REM filepath: /d:/azalise_ai_git/azalise_ai/setup_azalise.bat
@echo off
title Azalise AI Setup
echo Configuring Azalise AI Environment...

REM Create and activate virtual environment
python -m venv venv
call venv\Scripts\activate.bat

REM Clear pip cache
pip cache purge

REM Update pip and install build dependencies
python -m pip install --upgrade pip
pip install --no-cache-dir setuptools==75.3.0 wheel>=0.45.1

REM Install pandas dependencies with compatible versions
pip install --no-cache-dir python-dateutil>=2.8.2
pip install --no-cache-dir numpy==1.22.0
pip install --no-cache-dir pytz>=2025.1

REM Install pandas without dependencies
pip install --no-dependencies --no-cache-dir pandas==1.5.3

REM Install other packages with PEP 517
pip install --use-pep517 --no-cache-dir colorama==0.4.6 pyinput==0.3.2
pip install --use-pep517 --no-cache-dir redis==5.0.0 python-dotenv==0.21.0

REM Machine Learning Core
pip install torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121

REM Flash Attention Setup
echo Installing Flash Attention dependencies...
pip install --no-cache-dir packaging ninja setuptools wheel
echo This can take from 5 minutes to 2 hours depending on your system. Please be patient.
pip install --no-cache-dir flash-attn==2.5.6 --no-build-isolation

REM Audio Processing
pip install --use-pep517 --no-cache-dir pyaudio==0.2.13 pynput==0.3.2 pydub==0.25.1 librosa==0.10.0 pygame==2.6.1
pip install --use-pep517 --no-cache-dir soundfile==0.12.1 wave==0.0.2 SpeechRecognition==3.10.0 sounddevice==0.4.5

REM Machine Learning & AI
pip install --use-pep517 --no-cache-dir transformers==4.48.3 sentence-transformers==3.4.1 timm==0.9.2
pip install --use-pep517 --no-cache-dir wandb==0.15.5 protobuf==3.19.6 openai==1.63.0

REM Web & API
pip install --use-pep517 --no-cache-dir Flask==2.3.3 Werkzeug==2.3.7 requests==2.31.0 aiohttp==3.8.5
pip install --use-pep517 --no-cache-dir fastapi==0.115.8 starlette==0.45.3 uvicorn==0.34.0 aiofiles==24.1.0

REM Windows Specific
pip install --use-pep517 --no-cache-dir pywin32==306

REM Visualization
pip install --use-pep517 --no-cache-dir matplotlib==3.8.4

REM Special Installations
pip install --use-pep517 --no-cache-dir -U openai-whisper

REM Install TTS
pip install --use-pep517 --no-cache-dir TTS

echo.
echo Virtual environment setup complete. Starting Azalise AI...
echo.

REM Start the application
call start_all.bat

pause