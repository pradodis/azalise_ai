import sys, os, logging, threading, queue, tempfile, time
import torch, numpy as np, soundfile as sf, librosa, sounddevice as sd
import requests
from flask import Flask, request, Response, stream_with_context
from TTS.api import TTS
from pathlib import Path
from TTS.utils.manage import ModelManager

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import AUDIO_DEVICE_OUTPUT, TTS_CONFIG

app = Flask(__name__)

# Add connection tracking
client_connected = False

class TextToSpeechHandler:
    def __init__(self, audio_device_output=None):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.engine = TTS_CONFIG.get("engine", "coqui")
        
        if self.engine == "coqui":
            try:
                # Pré-carregar modelo em thread separada
                def load_model():
                    manager = ModelManager()
                    pt_models = [m for m in manager.list_models() if "/pt/" in m]
                    model_name = next((m for m in pt_models if "tacotron2-DDC" in m.lower()), pt_models[0])
                    self.tts = TTS(model_name).to(self.device)
                    self.model_ready = True
                    self.logger.info(f"Model loaded successfully on {self.device}")
                    
                threading.Thread(target=load_model).start()
                
            except Exception as e:
                self.logger.error(f"Failed to load TTS model: {e}")
                raise e
        
        self.elevenlabs_config = TTS_CONFIG.get("elevenlabs", {})

    def _get_device_sample_rate(self):
        return 48000  # Fixed sample rate for consistency

    def synthesize(self, text):
        """Generate audio file and return its path"""
        if self.engine == "elevenlabs":
            return self.synthesize_elevenlabs(text)
        return self.synthesize_coqui(text)

    def synthesize_coqui(self, text):
        try:
            # Usar diretório temporário específico e nomes mais curtos
            temp_dir = os.path.join(tempfile.gettempdir(), 'tts_cache')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Nome de arquivo mais curto usando hash
            temp_file = os.path.join(temp_dir, f"{hash(text)}.wav")
            
            # Verificar se já existe cache para este texto
            if os.path.exists(temp_file):
                return temp_file
                
            # Sintetizar diretamente para o arquivo
            self.tts.tts_to_file(
                text=text,
                file_path=temp_file,
                gpu=torch.cuda.is_available()  # Forçar uso de GPU se disponível
            )
            return temp_file
        except Exception as e:
            self.logger.error(f"Synthesis failed: {e}")
            return None

    def synthesize_elevenlabs(self, text):
        try:
            url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.elevenlabs_config['voice_id']}"
            headers = {
                "xi-api-key": self.elevenlabs_config["api_key"],
                "Content-Type": "application/json"
            }
            data = {
                "text": text,
                "model_id": self.elevenlabs_config["model_id"],
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }

            response = requests.post(url, json=data, headers=headers)
            if response.status_code == 200:
                temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="tts_").name
                with open(temp_file, "wb") as f:
                    f.write(response.content)
                return temp_file
            else:
                self.logger.error(f"ElevenLabs API error: {response.status_code}")
                return None
        except Exception as e:
            self.logger.error(f"ElevenLabs synthesis failed: {e}")
            return None

@app.route('/synthesize', methods=['POST'])
def synthesize_speech():
    try:
        data = request.get_json(force=True)  # Mais rápido que request.json
        text = data.get('text')
        if not text: 
            return {"error": "No text provided"}, 400
        
        # Processar em thread separada para não bloquear
        def process():
            temp_file = tts_handler.synthesize(text)
            if temp_file:
                return {"file_path": temp_file}
            return {"error": "Synthesis failed"}, 500
            
        result = process()
        return result, 200 if "file_path" in result else 500
        
    except Exception as e:
        return {"error": f"Server error: {str(e)}"}, 500

@app.route('/', methods=['GET'])
def health_check():
    global client_connected
    # Check if this is a new connection
    if not client_connected:
        print(f"{time.strftime('%H:%M:%S')} [TTS] Cliente conectado")
        client_connected = True
    return {"status": "healthy", "service": "TTS Server", "message": "Connection established"}, 200

@app.errorhandler(500)
def handle_error(e):
    global client_connected
    if client_connected:
        print(f"{time.strftime('%H:%M:%S')} [TTS] Cliente desconectado")
        client_connected = False
    return {"error": str(e)}, 500

tts_handler = TextToSpeechHandler(audio_device_output=AUDIO_DEVICE_OUTPUT)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    sys.modules['flask.cli'].show_server_banner = lambda *x: None
    print("\n[TTS] Servidor TTS iniciado com sucesso em http://localhost:5501")
    print("[TTS] Aguardando conexões...")
    app.config['PROPAGATE_EXCEPTIONS'] = True
    app.run(
        host='localhost', 
        port=5501, 
        debug=False, 
        use_reloader=False,
        threaded=True,
        processes=1
    )