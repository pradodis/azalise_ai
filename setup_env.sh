#!/bin/bash

# Verificar versão do Python
python_version=$(python -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')
if [[ "$python_version" != "3.10.11" ]]; then
    echo "Error: Python 3.10.11 is required (found $python_version)"
    exit 1
fi

# Criar ambiente virtual
python -m venv venv

# Ativar ambiente virtual
source venv/Scripts/activate

# Limpar cache do pip
pip cache purge

# Atualizar pip e ferramentas de build
python -m pip install --upgrade pip
pip install --no-cache-dir setuptools==75.3.0 wheel>=0.45.1

# Core dependencies
pip install --no-cache-dir python-dateutil>=2.8.2
pip install --no-cache-dir numpy==1.22.0
pip install --no-cache-dir pytz>=2025.1
pip install --no-dependencies --no-cache-dir pandas==1.5.3

# Basic utilities
pip install --use-pep517 --no-cache-dir colorama==0.4.6 pyinput==0.3.2
pip install --use-pep517 --no-cache-dir redis==5.0.0 python-dotenv==0.21.0

# Machine Learning Core - CUDA 12.1
pip install torch==2.1.0+cu121 torchvision==0.16.0+cu121 torchaudio==2.1.0+cu121 --index-url https://download.pytorch.org/whl/cu121

# Flash Attention Setup
echo "Installing Flash Attention..."
pip install --no-cache-dir packaging ninja setuptools wheel
pip install --no-cache-dir flash-attn==2.5.6 --no-build-isolation

# Audio Processing
pip install --use-pep517 --no-cache-dir pyaudio==0.2.13 pynput==0.3.2 
pip install --use-pep517 --no-cache-dir pydub==0.25.1 librosa==0.10.0 
pip install --use-pep517 --no-cache-dir pygame==2.6.1
pip install --use-pep517 --no-cache-dir soundfile==0.12.1 
pip install --use-pep517 --no-cache-dir wave==0.0.2 
pip install --use-pep517 --no-cache-dir SpeechRecognition==3.10.0 
pip install --use-pep517 --no-cache-dir sounddevice==0.4.5

# Machine Learning & AI
pip install --use-pep517 --no-cache-dir transformers==4.36.2 
pip install --use-pep517 --no-cache-dir sentence-transformers==2.3.1 
pip install --use-pep517 --no-cache-dir timm==0.9.12
pip install --use-pep517 --no-cache-dir wandb==0.16.2 
pip install --use-pep517 --no-cache-dir protobuf==4.25.2 
pip install --use-pep517 --no-cache-dir openai==1.6.1

# Web & API
pip install --use-pep517 --no-cache-dir Flask==2.3.3 
pip install --use-pep517 --no-cache-dir Werkzeug==2.3.7 
pip install --use-pep517 --no-cache-dir requests==2.31.0 
pip install --use-pep517 --no-cache-dir aiohttp==3.9.1
pip install --use-pep517 --no-cache-dir fastapi==0.109.0 
pip install --use-pep517 --no-cache-dir starlette==0.35.1 
pip install --use-pep517 --no-cache-dir uvicorn==0.27.0.post1

# Windows Specific
pip install --use-pep517 --no-cache-dir pywin32==306

# Visualization
pip install --use-pep517 --no-cache-dir matplotlib==3.8.2

# Special Installations
pip install --use-pep517 --no-cache-dir -U openai-whisper
pip install --use-pep517 --no-cache-dir TTS==0.22.0

# Verificar instalação do CUDA
if ! nvidia-smi &> /dev/null; then
    echo "Warning: NVIDIA GPU/CUDA not detected"
    echo "Please ensure CUDA 12.1 is properly installed for optimal performance"
fi

echo "Environment setup complete. Activate with 'source venv/Scripts/activate'"