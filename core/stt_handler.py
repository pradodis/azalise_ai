from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import speech_recognition as sr
import whisper
import io, logging, sys, time
from pathlib import Path
import torch
import os
import numpy as np
from typing import Dict, Optional
import asyncio
from concurrent.futures import ThreadPoolExecutor
import tempfile
from pydantic import BaseModel

# Setup path and imports
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import STT_CONFIG

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stt_handler")

app = FastAPI()

# Global state
active_sessions: Dict[str, dict] = {}
thread_pool = ThreadPoolExecutor(max_workers=3)  # Limit concurrent transcriptions
model_cache = {}

async def init_whisper_model():
    """Initialize Whisper model asynchronously"""
    if STT_CONFIG["engine"] == "whisper":
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"[STT] Using device: {device}")
        
        # Run model loading in thread pool to not block
        return await asyncio.get_event_loop().run_in_executor(
            thread_pool,
            whisper.load_model,
            STT_CONFIG["whisper"]["model"],
            device
        )
    return None

# Initialize model on startup
whisper_model = None
@app.on_event("startup")
async def startup_event():
    global whisper_model
    whisper_model = await init_whisper_model()

async def transcribe_with_whisper(audio_path: str) -> str:
    """Asynchronous Whisper transcription"""
    try:
        # Run transcription in thread pool with optimized settings
        result = await asyncio.get_event_loop().run_in_executor(
            thread_pool,
            lambda: whisper_model.transcribe(
                audio_path,
                language=STT_CONFIG["whisper"]["language"],
                fp16=torch.cuda.is_available(),
                # Removed batch_size parameter
                beam_size=5,  # Add beam search for better accuracy
                best_of=5    # Consider top 5 transcriptions
            )
        )
        return result["text"]
    except Exception as e:
        logger.error(f"Whisper transcription error: {str(e)}")
        raise

async def transcribe_with_google(audio_data: bytes) -> str:
    """Asynchronous Google transcription"""
    recognizer = sr.Recognizer()
    wav_buffer = io.BytesIO(audio_data)
    
    try:
        with sr.AudioFile(wav_buffer) as source:
            audio = recognizer.record(source)
        # Run in thread pool as Google API is blocking
        return await asyncio.get_event_loop().run_in_executor(
            thread_pool,
            recognizer.recognize_google,
            audio,
            'pt-BR'
        )
    except Exception as e:
        logger.error(f"Google transcription error: {str(e)}")
        raise

@app.post("/transcribe")
async def transcribe(request: Request):
    """Optimized recording stop and transcription endpoint"""
    try:
        session_id = request.headers.get('X-Session-ID')
        if not session_id:
            raise HTTPException(status_code=400, detail="No session ID provided")
            
        if session_id not in active_sessions:
            raise HTTPException(status_code=403, detail="Invalid session")
            
        active_sessions[session_id]['last_activity'] = time.time()
        
        # Get audio data
        audio_data = await request.body()
        if not audio_data:
            raise HTTPException(status_code=400, detail="No audio data received")

        # Process audio based on engine type
        if STT_CONFIG["engine"] == "whisper":
            # Create temporary file for Whisper
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_file.write(audio_data)
                temp_path = temp_file.name

            try:
                text = await transcribe_with_whisper(temp_path)
            finally:
                os.unlink(temp_path)
        else:
            text = await transcribe_with_google(audio_data)
            
        logger.info(f"[STT] Transcribed text: {text}")
        
        return JSONResponse({
            "success": True,
            "text": text,
            "model": STT_CONFIG["whisper"]["model"] if STT_CONFIG["engine"] == "whisper" else "google"
        })
        
    except Exception as e:
        logger.error(f"[STT] Error: {str(e)}")
        return JSONResponse(
            status_code=400,
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
        logger.info(f"[STT] New client connected (Session: {session_id})")
    
    return {
        "status": "healthy",
        "service": "STT Server",
        "message": "Connection established"
    }

@app.post("/disconnect")
async def disconnect(request: Request):
    """Handle client disconnection"""
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        raise HTTPException(status_code=400, detail="No session ID provided")
    
    if session_id in active_sessions:
        del active_sessions[session_id]
        logger.info(f"[STT] Client disconnected (Session: {session_id})")
    
    return {"success": True, "message": "Disconnected successfully"}

if __name__ == "__main__":
    import uvicorn
    logger.info("\n[STT] STT Server started successfully at http://localhost:5502")
    logger.info("[STT] Waiting for connections...")
    uvicorn.run(app, host='localhost', port=5502, workers=1)