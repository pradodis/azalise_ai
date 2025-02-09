import sounddevice as sd
import numpy as np
import threading
import keyboard
import queue
import whisper
import torch
import time
from pathlib import Path
import wave
from datetime import datetime

class VoiceCapture:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.recording = False
        self.audio_queue = queue.Queue()
        self.recorded_frames = []
        self.model = whisper.load_model("base")
        self.start_time = None
        self.metrics = {
            'recording_time': 0,
            'processing_time': 0,
            'total_time': 0
        }
        
    def callback(self, indata, frames, time, status):
        if status:
            print(status)
        if self.recording:
            self.audio_queue.put(indata.copy())
            self.recorded_frames.append(indata.copy())

    def start_recording(self):
        self.recording = True
        self.recorded_frames = []
        self.start_time = datetime.now()
        print("Gravando... (Solte a tecla 0 para parar)")

    def stop_recording(self):
        self.recording = False
        if len(self.recorded_frames) > 0:
            # Calcula tempo de gravação
            recording_end = datetime.now()
            self.metrics['recording_time'] = (recording_end - self.start_time).total_seconds()
            print(f"\nTempo de gravação: {self.metrics['recording_time']:.2f} segundos")

            processing_start = time.time()
            
            # Concatena todos os frames
            audio_data = np.concatenate(self.recorded_frames, axis=0)
            
            # Salva temporariamente o áudio
            temp_file = Path("temp_recording.wav")
            with wave.open(str(temp_file), 'wb') as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(self.sample_rate)
                wf.writeframes((audio_data * 32767).astype(np.int16).tobytes())
            
            # Processa o áudio com Whisper
            print("Processando áudio...")
            transcription_start = time.time()
            result = self.model.transcribe(str(temp_file))
            
            # Calcula métricas de tempo
            processing_end = time.time()
            self.metrics['processing_time'] = processing_end - processing_start
            self.metrics['total_time'] = processing_end - self.start_time.timestamp()
            
            # Exibe resultados e métricas
            print("\n=== Métricas de Tempo ===")
            print(f"Tempo de gravação: {self.metrics['recording_time']:.2f}s")
            print(f"Tempo de processamento: {self.metrics['processing_time']:.2f}s")
            print(f"Tempo total: {self.metrics['total_time']:.2f}s")
            print(f"\nTexto reconhecido: {result['text']}")
            
            # Limpa os frames gravados
            self.recorded_frames = []
            temp_file.unlink()  # Remove o arquivo temporário

    def run(self):
        try:
            with sd.InputStream(channels=1,
                              samplerate=self.sample_rate,
                              callback=self.callback):
                print("Pressione e segure a tecla 0 para falar")
                
                while True:
                    if keyboard.is_pressed('0') and not self.recording:
                        self.start_recording()
                    elif not keyboard.is_pressed('0') and self.recording:
                        self.stop_recording()
                    time.sleep(0.1)

        except KeyboardInterrupt:
            print("\nCaptura de áudio finalizada.")
        except Exception as e:
            print(f"Erro: {e}")

if __name__ == "__main__":
    capture = VoiceCapture()
    capture.run()
