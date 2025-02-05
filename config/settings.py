# Audio settings
AUDIO_DEVICE_OUTPUT = 103
AUDIO_DEVICE_INPUT = 1

# TTS Server settings
TTS_SERVER_URL = "http://localhost:5501/synthesize"

# STT Server settings
STT_SERVER_URL = "http://localhost:5502/transcribe"

# API Configuration
API_CONFIG = {
    "api_type": "openai",  # "local" or "openai"
    "local_api": {
        "url": "http://127.0.0.1:5000/v1/chat/completions",
        "model": "Meta8BQ4"
    },
    "openai_api": {
        "url": "https://api.openai.com/v1/chat/completions",
        "api_key": "OPEN_AI_API_KEY", #Adjust your OpenAI API key
        "model": "gpt-4o-mini"
    }
}

# AI Instructions
COMMON_INSTRUCTION = "Responda de forma suscinta e objetiva. Não use emojis. A resposta deve ter entre 5 e 15 palavras. A resposta deve ser em portugues brasileiro. A conversa deve ocorrer com naturalidade. A AI é cabeça dura e tem gênio forte. A AI deve interpretar uma garota de 20 anos que é uma grande amiga."
