import os
from dotenv import load_dotenv

load_dotenv()

# STT Configuration
STT_SERVER_URL = "http://localhost:5502"  # Removido /transcribe para usar na verificação de conexão
STT_TRANSCRIBE_URL = "http://localhost:5502/transcribe"  # Nova URL específica para transcrição
STT_CONFIG = {
    "engine": "whisper",  # Options: "google" or "whisper"
    "whisper": {
        "model": "small",  # Options: "tiny", "base", "small", "medium", "large"
        "language": "pt"
    }
}

# TTS Configuration
TTS_SERVER_URL = "http://localhost:5501"  # Removido /synthesize para usar na verificação de conexão
TTS_SYNTHESIS_URL = "http://localhost:5501/synthesize"  # Nova URL específica para síntese
TTS_CONFIG = {
    "engine": "elevenlabs",
    "elevenlabs": {
        "api_key": os.getenv("ELEVENLABS_API_KEY"),
        "voice_id": os.getenv("ELEVENLABS_VOICE_ID"),
        "model_id": os.getenv("ELEVENLABS_MODEL_ID")
    }
}

# Audio Configuration
AUDIO_DEVICE_OUTPUT = 103
AUDIO_DEVICE_INPUT = 1

# API Configuration
API_CONFIG = {
    "api_type": os.getenv("API_TYPE", "openai"),
    "local_api": {
        "url": "http://localhost:5000/v1/chat/completions",
        "model": "Meta8BQ4"
    },
    "openai_api": {
        "url": "https://api.openai.com/v1/chat/completions",
        "api_key": os.getenv("OPENAI_API_KEY"),
        "model": os.getenv("OPENAI_MODEL")
    }
}

# Performance Tracking
TIME_CHECK = True
METRICS_ENABLED = True
METRICS_LOG_DIR = "performance_logs"

# AI Instructions
COMMON_INSTRUCTION = "Responda de forma suscinta e objetiva. Não use emojis. A resposta deve ter entre 10 e 25 palavras. A resposta deve ser em portugues brasileiro. A conversa deve ocorrer com naturalidade. A AI é cabeça dura e tem gênio forte, ela é doce mas tem uma malvadez oculta que sutilmente revela de vez em quando. A AI deve interpretar uma garota de 20 anos chamada Azalise, que é uma grande amiga. Azalise é uma Inteligência artificial criada por Diego Silva Prado."
