from flask import Flask, request, jsonify
import speech_recognition as sr
import io
import wave
import logging
import os
import sys

# Configure logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

app = Flask(__name__)
app.logger.disabled = True

recognizer = sr.Recognizer()

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        # Get audio data from request
        audio_data = request.get_data()
        
        # Create WAV file in memory
        wav_buffer = io.BytesIO(audio_data)
        
        # Convert to format compatible with speech_recognition
        with sr.AudioFile(wav_buffer) as source:
            audio = recognizer.record(source)
            
        # Perform speech recognition
        text = recognizer.recognize_google(audio, language='pt-BR')
        return jsonify({"success": True, "text": text})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == "__main__":
    print("\n[STT] Server started successfully on http://localhost:5502")
    app.run(host='localhost', port=5502, debug=False, use_reloader=False)