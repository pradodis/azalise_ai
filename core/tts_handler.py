import sys, os, logging, threading, queue, tempfile, time
import torch, numpy as np, soundfile as sf, librosa, sounddevice as sd
from flask import Flask, request
from TTS.api import TTS
from pathlib import Path

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import AUDIO_DEVICE_OUTPUT

app = Flask(__name__)

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
        
        audio_files = tts_handler.synthesize(text, speaker_wav)
        return ({"message": "Audio synthesis started", "files_queued": len(audio_files)}, 200) if audio_files else ({"error": "Synthesis failed"}, 500)
    except Exception as e:
        return {"error": f"Server error: {str(e)}"}, 500

tts_handler = TextToSpeechHandler(audio_device_output=AUDIO_DEVICE_OUTPUT)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    sys.modules['flask.cli'].show_server_banner = lambda *x: None
    print("\n[TTS] Server started successfully on http://localhost:5501")
    app.run(host='localhost', port=5501, debug=False, use_reloader=False)