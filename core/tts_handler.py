from flask import Flask, request, send_file
from TTS.api import TTS
import torch
import os
import tempfile
import logging
import sys

app = Flask(__name__)

class TextToSpeechHandler:
    def __init__(self):
        # Force CPU usage to avoid CUDA/cuDNN warnings
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
        logging.info("TTS model initialized in CPU mode")
        
    def synthesize(self, text, speaker_wav):
        try:
            temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            self.tts.tts_to_file(
                text=text.rstrip('.'),
                file_path=temp_file.name,
                speaker_wav=speaker_wav,
                language="pt"
            )
            return temp_file.name
        except Exception as e:
            logging.error(f"Error during synthesis: {str(e)}")
            return None

tts_handler = TextToSpeechHandler()

@app.route('/synthesize', methods=['POST'])
def synthesize_speech():
    data = request.json
    text = data.get('text')
    speaker_wav = data.get('speaker_wav', "D:\\oobabooga\\text-generation-webui-2.4\\extensions\\coqui_tts\\voices\\Mini_Dina.wav")
    
    if not text:
        return {"error": "No text provided"}, 400
    
    audio_file = tts_handler.synthesize(text, speaker_wav)
    if audio_file:
        response = send_file(audio_file, mimetype="audio/wav")
        # Clean up the temporary file after sending
        @response.call_on_close
        def cleanup():
            os.unlink(audio_file)
        return response
    return {"error": "Synthesis failed"}, 500

if __name__ == "__main__":
    # Configure logging
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    cli = sys.modules['flask.cli']
    cli.show_server_banner = lambda *x: None
    
    print("\n[TTS] Server started successfully on http://localhost:5501")
    app.run(host='localhost', port=5501, debug=False, use_reloader=False)