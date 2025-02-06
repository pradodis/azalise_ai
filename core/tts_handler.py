import sys, os, logging, threading, queue, tempfile, time
import torch, numpy as np, soundfile as sf, librosa, sounddevice as sd
from flask import Flask, request, Response, stream_with_context
from TTS.api import TTS
from pathlib import Path

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import AUDIO_DEVICE_OUTPUT

app = Flask(__name__)

# Add connection tracking
client_connected = False

class TextToSpeechHandler:
    def __init__(self, audio_device_output=None):
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
        self.audio_device = audio_device_output
        self.target_sample_rate = self._get_device_sample_rate()
        self.audio_queue = queue.Queue()
        self.is_playing = False
        self.chunk_size = 12 # Number of frames to stream at once
        self.chunk_samples = 1024  # Tamanho do chunk para streaming
        self.stream_buffer = queue.Queue()
        self.current_stream = None
        threading.Thread(target=self._process_queue, daemon=True).start()

    def _get_device_sample_rate(self):
        try:
            return int(sd.query_devices(self.audio_device)['default_samplerate'])
        except:
            return 48000

    def _resample_audio(self, audio_path):
        y, sr = librosa.load(audio_path, sr=None)
        if sr != self.target_sample_rate:
            y_resampled = librosa.resample(y, orig_sr=sr, target_sr=self.target_sample_rate)
            sf.write(audio_path, y_resampled, self.target_sample_rate, 'PCM_16')

    def synthesize(self, text, speaker_wav):
        if not os.path.exists(speaker_wav):
            self.logger.error(f"Speaker file not found: {speaker_wav}")
            return None

        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False, prefix="tts_").name
        try:
            self.tts.tts_to_file(text=text, file_path=temp_file, speaker_wav=speaker_wav, language="pt")
            self._resample_audio(temp_file)
            self.audio_queue.put(temp_file)
            return [temp_file]
        except Exception as e:
            if os.path.exists(temp_file): os.unlink(temp_file)
            self.logger.error(f"Synthesis failed: {e}")
            return None

    def stream_synthesis(self, text, speaker_wav):
        try:
            # Gera o áudio completo primeiro
            wav = self.tts.tts(text=text, speaker_wav=speaker_wav, language="pt")
            
            # Converte tensor PyTorch para numpy array
            wav = wav.numpy() if hasattr(wav, 'numpy') else np.array(wav)
            
            # Resampling para a taxa do dispositivo se necessário
            if self.target_sample_rate != 24000:  # XTTS usa 22050Hz
                wav = librosa.resample(wav, orig_sr=24000, target_sr=self.target_sample_rate)
            
            wav = np.clip(wav, -1.0, 1.0).astype(np.float32)
            
            # Converte para stereo se necessário
            if len(wav.shape) == 1:
                wav = np.column_stack((wav, wav))
            
            # Divide o áudio em chunks e coloca no buffer
            for i in range(0, len(wav), self.chunk_samples):
                chunk = wav[i:i + self.chunk_samples]
                if len(chunk) < self.chunk_samples:
                    # Pad último chunk se necessário
                    chunk = np.pad(chunk, ((0, self.chunk_samples - len(chunk)), (0, 0)))
                self.stream_buffer.put(chunk)
            
            # Marca o fim do stream
            self.stream_buffer.put(None)
            return True
            
        except Exception as e:
            self.logger.error(f"Streaming synthesis failed: {e}")
            return False

    def _stream_audio(self):
        try:
            with sd.OutputStream(
                samplerate=self.target_sample_rate,  # Usa a taxa do dispositivo
                channels=2,
                device=self.audio_device,
                dtype=np.float32,
                latency='low'
            ) as stream:
                while True:
                    chunk = self.stream_buffer.get()
                    if chunk is None:  # End of stream
                        break
                    stream.write(chunk)
                    self.stream_buffer.task_done()
        except Exception as e:
            self.logger.error(f"Streaming playback error: {e}")

    def start_streaming(self):
        if self.current_stream is None or not self.current_stream.is_alive():
            self.current_stream = threading.Thread(target=self._stream_audio, daemon=True)
            self.current_stream.start()

    def _process_queue(self):
        while True:
            try:
                self._play_audio(self.audio_queue.get())
            except Exception as e:
                self.logger.error(f"Playback error: {e}")
            finally:
                time.sleep(0.1)

    def _play_audio(self, audio_file):
        if not os.path.exists(audio_file): return
        try:
            self.is_playing = True
            audio_data, sr = sf.read(audio_file)
            audio_data = np.clip(audio_data.astype(np.float32), -1.0, 1.0)
            if len(audio_data.shape) == 1:
                audio_data = np.column_stack((audio_data, audio_data))

            try:
                with sd.OutputStream(samplerate=sr, channels=audio_data.shape[1],
                                  device=self.audio_device, dtype=np.float32,
                                  latency='low', blocksize=2048) as stream:
                    stream.write(audio_data)
            except sd.PortAudioError:
                resampled = librosa.resample(audio_data.T, orig_sr=sr, target_sr=self.target_sample_rate)
                with sd.OutputStream(samplerate=self.target_sample_rate,
                                  channels=2, device=self.audio_device,
                                  dtype=np.float32, latency='low') as stream:
                    stream.write(resampled.T)
        finally:
            self.is_playing = False
            if os.path.exists(audio_file): os.unlink(audio_file)
            self.audio_queue.task_done()

@app.route('/synthesize', methods=['POST'])
def synthesize_speech():
    try:
        data = request.json
        text = data.get('text')
        speaker_wav = data.get('speaker_wav', "D:\\oobabooga\\text-generation-webui-2.4\\extensions\\coqui_tts\\voices\\Mini_Dina.wav")
        if not text: return {"error": "No text provided"}, 400
        
        # Start streaming synthesis
        tts_handler.start_streaming()
        success = tts_handler.stream_synthesis(text, speaker_wav)
        
        return ({"message": "Streaming synthesis started"}, 200) if success else ({"error": "Synthesis failed"}, 500)
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
    app.run(host='localhost', port=5501, debug=False, use_reloader=False)