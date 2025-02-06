# Audio settings
AUDIO_DEVICE_OUTPUT = 103
AUDIO_DEVICE_INPUT = 1

# TTS Server settings
TTS_SERVER_URL = "http://localhost:5501"  # Removido /synthesize para usar na verificação de conexão
TTS_SYNTHESIS_URL = "http://localhost:5501/synthesize"  # Nova URL específica para síntese

# STT Server settings
STT_SERVER_URL = "http://localhost:5502"  # Removido /transcribe para usar na verificação de conexão
STT_TRANSCRIBE_URL = "http://localhost:5502/transcribe"  # Nova URL específica para transcrição

# STT Configuration
STT_CONFIG = {
    "engine": "google",  # Options: "google" or "whisper"
    "whisper": {
        "model": "medium",  # Options: "tiny", "base", "small", "medium", "large"
        "language": "pt"
    }
}

# API Configuration
API_CONFIG = {
    "api_type": "openai",  # "local" ou "openai"
    "local_api": {
        "url": "http://127.0.0.1:5000/v1/chat/completions",
        "model": "Meta8BQ4"
    },
    "openai_api": {
        "url": "https://api.openai.com/v1/chat/completions", 
        "api_key": open("D:/Azalise_AI/openai_api.txt").read().strip(),
        "model": "gpt-4o-mini"
    }
}

# Debug
TIME_CHECK = True
FAKE_IA_RESPONSE = False
BENCHMARK_INPUT = False

# AI Instructions
COMMON_INSTRUCTION = "Responda de forma suscinta e objetiva. Não use emojis. A resposta deve ter entre 10 e 25 palavras. A resposta deve ser em portugues brasileiro. A conversa deve ocorrer com naturalidade. A AI é cabeça dura e tem gênio forte, ela é doce mas tem uma malvadez oculta que sutilmente revela de vez em quando. A AI deve interpretar uma garota de 20 anos chamada Azalise, que é uma grande amiga. Azalise é uma Inteligência artificial criada por Diego Silva Prado."
