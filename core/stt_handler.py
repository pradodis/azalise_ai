from flask import Flask, request, jsonify
import speech_recognition as sr
import io
import logging
import sys
from pathlib import Path

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import STT_METHOD

# Configure logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

app = Flask(__name__)
app.logger.disabled = True

recognizer = sr.Recognizer()

def transcribe_with_google(audio):
    return recognizer.recognize_google(audio, language='pt-BR')

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        audio_data = request.get_data()
        wav_buffer = io.BytesIO(audio_data)
        
        with sr.AudioFile(wav_buffer) as source:
            audio = recognizer.record(source)
        
        text = transcribe_with_google(audio)
        return jsonify({"success": True, "text": text})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == "__main__":
    print("\n[STT] Server started successfully on http://localhost:5502")
    app.run(host='localhost', port=5502, debug=False, use_reloader=False)