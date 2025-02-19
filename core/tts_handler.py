import sys, os, logging, tempfile, time
import torch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from TTS.api import TTS
from pathlib import Path
import pygame
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Optional
import aiofiles

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import AUDIO_DEVICE_OUTPUT, TTS_CONFIG, TIME_CHECK
from core.metrics import PerformanceMetrics

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tts_handler")

# Define lifespan before creating FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI application"""
    global tts_handler
    try:
        logger.info("Initializing TTS handler...")
        tts_handler = await TTSHandler.create()
        yield
    finally:
        if tts_handler:
            logger.info("Cleaning up TTS handler...")
            await tts_handler.cleanup()

# Initialize FastAPI with lifespan
app = FastAPI(lifespan=lifespan)

# Global state
active_sessions: Dict[str, dict] = {}
thread_pool = ThreadPoolExecutor(max_workers=4)
metrics = PerformanceMetrics()
tts_handler = None

class AsyncAudioPlayer:
    def __init__(self):
        self.initialized = False
        self.lock = asyncio.Lock()
        self.queue = asyncio.Queue()
        self.player_task = None
        
    async def initialize(self):
        if not self.initialized:
            await asyncio.get_event_loop().run_in_executor(None, self._init_pygame)
            self.player_task = asyncio.create_task(self._process_queue())
            self.initialized = True
            
    def _init_pygame(self):
        pygame.init()
        pygame.mixer.init(
            frequency=48000,
            size=-16,
            channels=2,
            buffer=256
        )
            
    async def play_audio(self, file_path: str, delete_after: bool = True):
        """Add audio file to queue instead of playing directly"""
        if not self.initialized:
            await self.initialize()
        
        # Add to queue and return immediately
        await self.queue.put((file_path, delete_after))
        return True
            
    async def _process_queue(self):
        """Background task to process audio queue"""
        while True:
            try:
                # Wait for next item in queue
                file_path, delete_after = await self.queue.get()
                
                try:
                    async with self.lock:
                        # Play current audio
                        await asyncio.get_event_loop().run_in_executor(
                            None,
                            self._play_and_wait,
                            file_path
                        )
                        
                        if delete_after:
                            try:
                                os.unlink(file_path)
                            except Exception as e:
                                logger.warning(f"Failed to delete file: {e}")
                                
                except Exception as e:
                    logger.error(f"Error playing audio: {e}")
                finally:
                    # Mark task as done even if there was an error
                    self.queue.task_done()
                    
            except Exception as e:
                logger.error(f"Queue processor error: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on error

    def _play_and_wait(self, file_path: str):
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                
            pygame.mixer.music.load(file_path)
            pygame.mixer.music.play()
            
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
                
            pygame.mixer.music.unload()
            
        except Exception as e:
            logger.error(f"Pygame playback error: {e}")
            raise

    async def cleanup(self):
        """Cleanup player resources"""
        if self.player_task:
            self.player_task.cancel()
            try:
                await self.player_task
            except asyncio.CancelledError:
                pass
        # Wait for remaining items
        if hasattr(self, 'queue'):
            await self.queue.join()
        
        if hasattr(self, 'lock'):
            async with self.lock:
                if pygame.mixer.get_init():
                    pygame.mixer.quit()

class TTSHandler:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.engine = TTS_CONFIG.get("engine", "coqui")
        self.audio_player = AsyncAudioPlayer()
        self.model_ready = asyncio.Event()
        self.elevenlabs_config = TTS_CONFIG.get("elevenlabs", {})
        self.tts = None
        
    @classmethod
    async def create(cls):
        """Factory method to create and initialize TTSHandler"""
        instance = cls()
        await instance.initialize_model()
        return instance

    async def initialize_model(self):
        if self.engine == "coqui":
            try:
                # Load model in thread pool
                await asyncio.get_event_loop().run_in_executor(
                    thread_pool,
                    self._load_coqui_model
                )
                self.model_ready.set()
            except Exception as e:
                logger.error(f"Failed to load TTS model: {e}")
                raise

    def _load_coqui_model(self):
        """Initialize Coqui TTS model"""
        try:
            logger.info("Loading Coqui TTS model...")
            if "coqui" not in TTS_CONFIG:
                raise ValueError("Missing 'coqui' configuration in TTS_CONFIG")
            if "model_name" not in TTS_CONFIG["coqui"]:
                raise ValueError("Missing 'model_name' in TTS_CONFIG['coqui']")
                
            model_name = TTS_CONFIG["coqui"]["model_name"]
            logger.info(f"Using Coqui model: {model_name}")
            
            self.tts = TTS(
                model_name=model_name,
                progress_bar=False,
                gpu=torch.cuda.is_available()
            )
            logger.info("Coqui TTS model loaded successfully")
        except KeyError as e:
            logger.error(f"Configuration error: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load Coqui model: {e}")
            raise

    async def synthesize(self, text: str) -> dict:
        """Main synthesis method that routes to appropriate engine"""
        if TIME_CHECK:
            metrics.start_timer('tts')
            
        try:
            if self.engine == "elevenlabs":
                result = await self.synthesize_elevenlabs(text)
            else:
                # Wait for model to be ready
                await self.model_ready.wait()
                result = await self.synthesize_coqui(text)
                
            if TIME_CHECK and result.get("success"):
                metrics.stop_timer('tts')
                
            return result
        except Exception as e:
            logger.error(f"Synthesis failed: {e}")
            return {"success": False, "error": str(e)}

    async def synthesize_coqui(self, text: str) -> dict:
        try:
            # Create temp file
            temp_dir = os.path.join(tempfile.gettempdir(), 'tts_cache')
            os.makedirs(temp_dir, exist_ok=True)
            temp_file = os.path.join(temp_dir, f"{int(time.time())}_{hash(text)}.wav")
            
            # Run synthesis in thread pool
            await asyncio.get_event_loop().run_in_executor(
                thread_pool,
                self._run_coqui_synthesis,
                text,
                temp_file
            )
            
            # Play audio asynchronously
            await self.audio_player.play_audio(temp_file)
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Coqui synthesis failed: {e}")
            return {"success": False, "error": str(e)}
            
    def _run_coqui_synthesis(self, text: str, file_path: str):
        self.tts.tts_to_file(
            text=text,
            file_path=file_path,
            gpu=torch.cuda.is_available()
        )

    async def synthesize_elevenlabs(self, text: str) -> dict:
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_config['voice_id']}"
            headers = {
                "xi-api-key": self.elevenlabs_config["api_key"],
                "Content-Type": "application/json",
                "Accept": "audio/mpeg"
            }
            data = {
                "text": text,
                "model_id": self.elevenlabs_config["model_id"],
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }

            async with aiofiles.tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False, prefix="tts_"
            ) as temp_file:
                # Make API request with aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=data, headers=headers) as response:
                        if response.status == 200:
                            audio_data = await response.read()
                            await temp_file.write(audio_data)
                            temp_path = temp_file.name

                # Play audio asynchronously
                await self.audio_player.play_audio(temp_path)
                return {"success": True}
        except Exception as e:
            logger.error(f"ElevenLabs synthesis failed: {e}")
            return {"success": False, "error": str(e)}

    async def cleanup(self):
        """Cleanup resources"""
        if hasattr(self, 'audio_player'):
            await self.audio_player.cleanup()
        if hasattr(self, 'tts'):
            self.tts = None

@app.post("/synthesize")
async def synthesize_speech(request: Request):
    try:
        if not tts_handler:
            return JSONResponse(
                status_code=503,
                content={"success": False, "error": "TTS handler not initialized"}
            )

        data = await request.json()
        text = data.get('text')
        if not text:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "No text provided"}
            )
            
        session_id = request.headers.get('X-Session-ID')
        if session_id:
            active_sessions[session_id]['last_activity'] = time.time()
            
        result = await tts_handler.synthesize(text)
        return JSONResponse(
            content=result,
            status_code=200 if result["success"] else 500
        )
    except Exception as e:
        logger.error(f"Error in synthesis endpoint: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "error": str(e)}
        )

@app.get("/")
async def root(request: Request):
    """Health check endpoint"""
    session_id = request.query_params.get('session_id') or request.headers.get('X-Session-ID')
    
    if session_id and session_id not in active_sessions:
        active_sessions[session_id] = {
            'connected_at': time.time(),
            'last_activity': time.time()
        }
        logger.info(f"New client connected (Session: {session_id})")
    
    return {
        "status": "healthy",
        "service": "TTS Server",
        "message": "Connection established"
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("\n[TTS] TTS Server started successfully at http://localhost:5501")
    logger.info("[TTS] Waiting for connections...")
    uvicorn.run(app, host='localhost', port=5501, workers=1)