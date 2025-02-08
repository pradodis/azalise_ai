from flask import Flask, request, jsonify, session
import speech_recognition as sr
import whisper
import io, logging, sys, time
from pathlib import Path
import torch

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import STT_CONFIG

# Configure logging
logging.getLogger('werkzeug').setLevel(logging.ERROR)
cli = sys.modules['flask.cli']
cli.show_server_banner = lambda *x: None

app = Flask(__name__)
app.logger.disabled = True

recognizer = sr.Recognizer()

# Add connection tracking
client_connected = False

# Add session management
active_sessions = {}

# Initialize Whisper model
whisper_model = None
if STT_CONFIG["engine"] == "whisper":
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[STT] Using device: {device}")
    whisper_model = whisper.load_model(STT_CONFIG["whisper"]["model"]).to(device)

def transcribe_with_google(audio):
    return recognizer.recognize_google(audio, language='pt-BR')

def transcribe_with_whisper(audio_data):
    try:
        result = whisper_model.transcribe(
            audio_data, 
            language=STT_CONFIG["whisper"]["language"],
            fp16=torch.cuda.is_available()  # Enable half-precision if using GPU
        )
        return result["text"]
    except Exception as e:
        logging.error(f"Whisper transcription error: {str(e)}")
        raise

def transcribe_audio_data(audio):
    if STT_CONFIG["engine"] == "whisper":
        return transcribe_with_whisper(audio)
    else:
        return transcribe_with_google(audio)

@app.route('/transcribe', methods=['POST'])
def transcribe_audio():
    try:
        session_id = request.headers.get('X-Session-ID')
        print(f"{time.strftime('%H:%M:%S')} [STT] Recebida requisição de transcrição (Session: {session_id})")
        print(f"{time.strftime('%H:%M:%S')} [STT] Sessões ativas: {list(active_sessions.keys())}")
        
        if not session_id:
            return jsonify({"success": False, "error": "No session ID provided"}), 400
            
        if session_id in active_sessions:
            active_sessions[session_id]['last_activity'] = time.time()
            
            audio_data = request.get_data()
            wav_buffer = io.BytesIO(audio_data)
            
            if STT_CONFIG["engine"] == "whisper":
                # For Whisper, we need to save the audio temporarily
                import tempfile
                import os
                
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                temp_file.write(audio_data)
                temp_file.close()
                
                try:
                    text = transcribe_with_whisper(temp_file.name)
                finally:
                    os.unlink(temp_file.name)
            else:
                with sr.AudioFile(wav_buffer) as source:
                    audio = recognizer.record(source)
                text = transcribe_with_google(audio)
            
            return jsonify({"success": True, "text": text})
        else:
            print(f"{time.strftime('%H:%M:%S')} [STT] Sessão inválida: {session_id}")
            return jsonify({"success": False, "error": "Invalid session"}), 403
            
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} [STT] Erro: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 400

@app.route('/', methods=['GET'])
def health_check():
    global client_connected
    session_id = request.args.get('session_id')
    
    if not session_id:
        return {"status": "error", "message": "No session ID provided"}, 400
        
    if session_id not in active_sessions:
        active_sessions[session_id] = {
            'connected_at': time.time(),
            'last_activity': time.time()
        }
        print(f"{time.strftime('%H:%M:%S')} [STT] Novo cliente conectado (Session: {session_id})")
        print(f"{time.strftime('%H:%M:%S')} [STT] Sessões ativas: {list(active_sessions.keys())}")
        client_connected = True
    else:
        active_sessions[session_id]['last_activity'] = time.time()
        
    return {"status": "healthy", "service": "STT Server", "message": "Connection established"}, 200

def cleanup_session(session_id):
    if session_id in active_sessions:
        print(f"{time.strftime('%H:%M:%S')} [STT] Cliente desconectado (Session: {session_id})")
        del active_sessions[session_id]
        if not active_sessions:
            global client_connected
            print(f"{time.strftime('%H:%M:%S')} [STT] Todos os clientes desconectados")
            client_connected = False

@app.route('/disconnect', methods=['POST'])
def disconnect():
    session_id = request.headers.get('X-Session-ID')
    if not session_id:
        return jsonify({"success": False, "error": "No session ID provided"}), 400
    
    cleanup_session(session_id)
    return jsonify({"success": True, "message": "Disconnected successfully"}), 200

@app.errorhandler(500)
def handle_error(e):
    session_id = request.headers.get('X-Session-ID')
    if session_id:
        cleanup_session(session_id)
    return {"error": str(e)}, 500

if __name__ == "__main__":
    print("\n[STT] Servidor STT iniciado com sucesso em http://localhost:5502")
    print("[STT] Aguardando conexões...")
    app.run(host='localhost', port=5502, debug=False, use_reloader=False)