import sys, os, logging, threading, queue, tempfile, time
import torch, numpy as np, soundfile as sf, librosa, sounddevice as sd
import requests
from flask import Flask, request, Response, stream_with_context
from TTS.api import TTS
from pathlib import Path
from TTS.utils.manage import ModelManager
import pygame

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import AUDIO_DEVICE_OUTPUT, TTS_CONFIG, TIME_CHECK
from core.metrics import PerformanceMetrics

app = Flask(__name__)

# Add connection tracking
client_connected = False

# Add global metrics instance
metrics = PerformanceMetrics()

class AudioPlayer:
    def __init__(self):
        pygame.init()
        pygame.mixer.init(
            frequency=48000,
            size=-16,
            channels=2,
            buffer=256
        )
        self.is_playing = False
        self.lock = threading.Lock()
        self.current_file = None
        self.cleanup_thread = None

    def play_audio(self, file_path, delete_after=True):
        try:
            print(f"[AudioPlayer] Iniciando reprodução do arquivo: {file_path}")
            with self.lock:
                # Stop any currently playing audio
                if pygame.mixer.music.get_busy():
                    print("[AudioPlayer] Parando áudio anterior")
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                
                # Check if file exists and has content
                if not os.path.exists(file_path):
                    print(f"[AudioPlayer] Erro: Arquivo não existe: {file_path}")
                    return False
                    
                file_size = os.path.getsize(file_path)
                if file_size == 0:
                    print("[AudioPlayer] Erro: Arquivo de áudio vazio")
                    return False
                    
                print(f"[AudioPlayer] Carregando arquivo ({file_size} bytes)")
                pygame.mixer.music.load(file_path)
                print("[AudioPlayer] Iniciando playback")
                pygame.mixer.music.play()
                
                # Start cleanup thread
                if self.cleanup_thread and self.cleanup_thread.is_alive():
                    self.cleanup_thread.join()
                self.cleanup_thread = threading.Thread(
                    target=self._wait_and_cleanup, 
                    args=(file_path, delete_after)
                )
                self.cleanup_thread.daemon = True
                self.cleanup_thread.start()
                
        except Exception as e:
            print(f"[AudioPlayer] Erro ao reproduzir áudio: {str(e)}")
            return False
        return True

    def _wait_and_cleanup(self, file_path, delete_after):
        try:
            # Wait for playback to complete
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            
            # Cleanup after playback
            pygame.mixer.music.unload()
            if delete_after and os.path.exists(file_path):
                try:
                    os.unlink(file_path)
                except Exception as e:
                    print(f"Aviso: Falha ao deletar arquivo: {e}")
        except Exception as e:
            print(f"Erro no cleanup do áudio: {e}")

    def __del__(self):
        # Cleanup on object destruction
        if self.current_file and os.path.exists(self.current_file):
            try:
                pygame.mixer.music.unload()
                os.unlink(self.current_file)
            except Exception:
                pass

class TextToSpeechHandler:
    def __init__(self, audio_device_output=None):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.engine = TTS_CONFIG.get("engine", "coqui")
        self.audio_player = AudioPlayer()
        
        if self.engine == "coqui":
            try:
                # Pré-carregar modelo em thread separada
                def load_model():
                    manager = ModelManager()
                    pt_models = [m for m in manager.list_models() if "/pt/" in m]
                    model_name = next((m for m in pt_models if "tacotron2-DDC" in m.lower()), pt_models[0])
                    self.tts = TTS(model_name).to(self.device)
                    self.model_ready = True
                    self.logger.info(f"Model loaded successfully on {self.device}")
                    
                threading.Thread(target=load_model).start()
                
            except Exception as e:
                self.logger.error(f"Failed to load TTS model: {e}")
                raise e
        
        self.elevenlabs_config = TTS_CONFIG.get("elevenlabs", {})

    def _get_device_sample_rate(self):
        return 48000  # Fixed sample rate for consistency

    def synthesize(self, text):
        """Generate audio file, play it and return success status"""
        if TIME_CHECK:
            metrics.start_timer('tts')
            
        result = self.synthesize_elevenlabs(text) if self.engine == "elevenlabs" else self.synthesize_coqui(text)
        
        if TIME_CHECK and result.get("success"):
            metrics.stop_timer('tts')
            # Removido print das métricas daqui, será feito apenas no run.py
            
        return result

    def synthesize_coqui(self, text):
        try:
            temp_dir = os.path.join(tempfile.gettempdir(), 'tts_cache')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Use a unique filename based on timestamp and text hash
            temp_file = os.path.join(temp_dir, f"{int(time.time())}_{hash(text)}.wav")
            
            # Ensure file doesn't exist
            if os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    temp_file = os.path.join(temp_dir, f"{int(time.time())}_{hash(text)}_{os.urandom(4).hex()}.wav")
            
            # Sintetizar diretamente para o arquivo
            self.tts.tts_to_file(
                text=text,
                file_path=temp_file,
                gpu=torch.cuda.is_available()
            )
            
            # Play audio directly
            self.audio_player.play_audio(temp_file, delete_after=True)
            return {"success": True}
            
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            return {"success": False, "error": str(e)}

    def synthesize_elevenlabs(self, text):
        try:
            print("[TTS] Iniciando síntese ElevenLabs")
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

            print("[TTS] Enviando requisição para ElevenLabs API")
            response = requests.post(url, json=data, headers=headers)
            print(f"[TTS] Status da resposta: {response.status_code}")
            
            if response.status_code == 200:
                print(f"[TTS] Content-Type recebido: {response.headers.get('Content-Type')}")
                content_length = len(response.content)
                print(f"[TTS] Tamanho do áudio recebido: {content_length} bytes")
                
                if content_length == 0:
                    print("[TTS] Erro: Resposta vazia da API")
                    return {"success": False, "error": "Empty response from API"}
                
                # Save as MP3 and play directly
                temp_file = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False, prefix="tts_").name
                print(f"[TTS] Salvando áudio em: {temp_file}")
                
                with open(temp_file, "wb") as f:
                    f.write(response.content)
                
                print("[TTS] Iniciando reprodução")
                if self.audio_player.play_audio(temp_file, delete_after=True):
                    print("[TTS] Reprodução iniciada com sucesso")
                    return {"success": True}
                else:
                    print("[TTS] Falha ao iniciar reprodução")
                    return {"success": False, "error": "Failed to play audio"}
            else:
                error_msg = f"ElevenLabs API error: {response.status_code}"
                print(f"[TTS] {error_msg}")
                try:
                    error_detail = response.json()
                    print(f"[TTS] Detalhes do erro: {error_detail}")
                except:
                    pass
                return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"ElevenLabs synthesis failed: {str(e)}"
            print(f"[TTS] {error_msg}")
            return {"success": False, "error": error_msg}

@app.route('/synthesize', methods=['POST'])
def synthesize_speech():
    try:
        data = request.get_json(force=True)  # Mais rápido que request.json
        text = data.get('text')
        if not text: 
            return {"success": False, "error": "No text provided"}, 400
        
        result = tts_handler.synthesize(text)
        return result, 200 if result["success"] else 500
        
    except Exception as e:
        return {"success": False, "error": f"Server error: {str(e)}"}, 500

@app.route('/', methods=['GET'])
def root():
    """Root endpoint for health checks"""
    session_id = request.args.get('session_id') or request.headers.get('X-Session-ID')
    
    if session_id:
        # Add session tracking if needed
        pass
        
    return {
        "status": "healthy",
        "service": "TTS Server",
        "message": "Connection established"
    }, 200

@app.errorhandler(500)
def handle_error(e):
    global client_connected
    if (client_connected):
        print(f"{time.strftime('%H:%M:%S')} [TTS] Cliente desconectado")
        client_connected = False
    return {"error": str(e)}, 500

tts_handler = TextToSpeechHandler(audio_device_output=AUDIO_DEVICE_OUTPUT)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    sys.modules['flask.cli'].show_server_banner = lambda *x: None
    print("\n[TTS] Servidor TTS iniciado com sucesso em http://localhost:5501")
    print("[TTS] Aguardando conexões...")
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.run(
        host='localhost', 
        port=5501, 
        debug=False, 
        use_reloader=False,
        threaded=True,
        processes=1
    )