## Azalise AI Voice Assistant
A voice assistant in Python that combines speech recognition, text-to-speech conversion, and AI-powered conversational features. The application offers a natural interface in Brazilian Portuguese, with its own personality, support for different model configurations, and an asynchronous architecture.

## Main Features

- Real-time audio recording and immediate processing.
- Speech-to-Text (STT) conversion using Google Speech API or Whisper.
- Text-to-Speech (TTS) conversion using Coqui-TTS or ElevenLabs.
- Natural conversational flow with OpenAI backend or local API.
- Primary language: Brazilian Portuguese.
- Integrated performance metrics and visualization (charts) generated via matplotlib.
- Configuration of audio input/output devices.
- Asynchronous architecture enabling better scalability and execution control.
- Optional GUI in PyQt5 for block diagram and real-time monitoring (interfaces/run_gui.py).
- Batch startup scripts for Windows (start_all.bat).

## Requirements

- Python 3.8 or higher
- Packages listed in requirements.txt, including (main ones):
- PyAudio
- TTS (Text-to-Speech)
- SpeechRecognition
- PyNput
- Flask
- Torch
- Whisper
- Colorama
- Pygame
- aiohttp
- matplotlib

## Installation

1. Clone the repository: git clone https://github.com/yourusername/azalise-ai.git
cd azalise-ai
2. Install dependencies (using venv or your preferred package manager): pip install -r requirements.txt
3. (Optional) Configure credentials if using Google Cloud Speech-to-Text or ElevenLabs:
    - Set the environment variable GOOGLE_APPLICATION_CREDENTIALS to your Google Cloud JSON path.
    - For ElevenLabs, add your key file in elevenlabs_api.txt (or adjust the path in config/settings.py).
    - Also configure your OpenAI API key in openai_api.txt or adjust in settings.py.

## Configuration

1. Copy `.env.example` to `.env`
2. Configure your API keys and settings in `.env`:
```bash
ELEVENLABS_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
...
```
3. Run `python core/audio_test.py` to find your audio device IDs
4. Update AUDIO_DEVICE_INPUT and AUDIO_DEVICE_OUTPUT in `.env`

## Quick Start
There are different ways to run the assistant:

1. Full Mode (Terminal)

- Open a terminal and run: python run.py
- Press and hold the '0' key on the numeric keypad to record audio. Release the key to convert audio to text.
- Press ESC to end the program.

2. Batch Startup Mode (Windows Only)

- Edit the start_all.bat file according to your installation (optional).
- Run start_all.bat, which will open several command windows: main server, TTS, and STT.

## Block Diagram GUI

Run the script run_gui.py to see a PyQt5 window displaying the block architecture and control buttons. python run_gui.py

# Architecture and Components

1. config/
- Contains configuration files (settings.py, etc.).
- Determines server URLs, STT/TTS parameters, and API keys.


2. core/
- Main interaction logic files, including:
- async_server_connection.py: Establishes asynchronous connections with STT/TTS.
- server_connection.py: Simplified synchronous version for server connection.
- stt_handler.py: Flask server managing local STT (Whisper or Google).
- tts_handler.py: Flask server for audio generation (Coqui-TTS or ElevenLabs), playback, and metrics.
- metrics.py: Records and reports processing times.
- run.py: Main “client-side” script connecting to STT/TTS servers, recording audio, and making AI requests.




3. interfaces/
- Scripts with graphical interface, such as run_gui.py, for showing the main flow diagram. (WIP)



4. start_all.bat (Windows)
- Script to start servers and the application in separate windows.

## Important Points

- API keys (Google Cloud, OpenAI, and ElevenLabs) are not included in the repository; you will need to configure them manually.
- The project has been tested on Windows; different configurations may be needed for other platforms (especially for audio devices).
- Make sure to update variables and paths in settings.py according to your environment.

## General Workflow

1. The user records audio (captured with PyAudio).
2. The audio is sent to the STT server (Whisper or Google) for transcription.
3. The transcribed text is processed by an AI model (OpenAI or local).
4. The text response is synthesized on the TTS server (Coqui or ElevenLabs).
5. The resulting audio is played locally.

## Execution Examples

1. Open a terminal and run (starting STT/TTS manually in other windows or via scripts):
2. python stt_handler.py (Default port: 5502)
3. python tts_handler.py (Default port: 5501)
4. python run.py

OR

1. Start everything via start_all.bat on Windows.

## Contributing

1. Fork the project.
2. Create your feature branch: git checkout -b my-feature
3. Commit your changes: git commit -m 'Add new feature'
4. Push to the branch: git push origin my-feature
5. Open a Pull Request in the original repository.

## License
This project is available under the MIT license. See the LICENSE file for more details.
This update includes mentions of STT/TTS server configurations, batch startup script (start_all.bat), execution flow, and key points that the project currently presents. Adjust as necessary to meet the specifics of your environment.
