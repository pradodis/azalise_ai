# Azalise AI Voice Assistant

A Python-based voice assistant that combines speech-to-text, text-to-speech, and AI conversation capabilities. It features a natural Brazilian Portuguese interface with a personalized AI personality.

## Features

- Real-time voice recording and processing
- Speech-to-text conversion using Google's recognition service
- Text-to-speech synthesis using XTTS v2
- Natural conversation flow with AI backend
- Brazilian Portuguese language support
- Configurable audio input/output devices

## Requirements

- Python 3.8+
- PyAudio
- TTS (Text-to-Speech)
- Speech Recognition
- PyNput
- Flask
- Torch
- Colorama

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/azalise-ai.git
cd azalise-ai
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure audio devices in `run.py`:
```python
audio_device_code_output = 40  # Change to your output device code
audio_device_code_input = 1    # Change to your input device code
```

## Usage

1. Start the TTS server:
```bash
python azalise_ai/core/tts_handler.py
```

2. Start the STT server:
```bash
python azalise_ai/core/stt_handler.py
```

3. Run the main application:
```bash
python azalise_ai/run.py
```

4. Control commands:
- Hold '0' to record your voice
- Release '0' to process and get AI response
- Press 'ESC' to exit

## Configuration

Adjust settings in `config/settings.py` to customize:
- API endpoints
- Voice settings
- Language preferences
- Audio file paths
- Output device configuration

## License

MIT License