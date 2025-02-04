from colorama import init, Fore, Style
from pynput import keyboard
import threading
import time
import io
import wave
import pyaudio
import requests
import json
from TTS.api import TTS
import torch
import tempfile
import os

history = []
commom_instuction = "Responda de forma suscinta e objetiva. Não use emojis. A resposta deve ter entre 5 e 15 palavras. A resposta deve ser em portugues brasileiro. A conversa deve ocorrer com naturalidade. A AI é cabeça dura e tem gênio forte. A AI deve interpretar uma garota de 20 anos que é uma grande amiga."
audio_device_code_output = 40  # Change this to your desired audio device code
audio_device_code_input = 1  # Change this to your desired audio device code

class VoiceRecorder:
    def __init__(self):
        init()  # Initialize colorama
        self.is_recording = False
        self.audio_data = []
        self.recording_thread = None
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        self.output_device_index = None
        
        self.output_device_index = audio_device_code_output
        self.api_url = "http://127.0.0.1:5000/v1/chat/completions"

        # Simple initialization message
        print("Sistema inicializado com sucesso!")
        print("Pressione e segure '0' para gravar, solte para converter para texto.")
        print("Pressione 'ESC' para sair.\n")
        
        # Get device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tts_server_url = "http://localhost:5501/synthesize"

    def list_audio_devices(self):
        print("\nAvailable Audio Input Devices:")
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if dev_info['maxInputChannels'] > 0:  # Show input devices
                print(f"Device {i}: {dev_info['name']}")
                
        print("\nAvailable Audio Output Devices:")
        for i in range(self.p.get_device_count()):
            dev_info = self.p.get_device_info_by_index(i)
            if dev_info['maxOutputChannels'] > 0:  # Show output devices
                print(f"Device {i}: {dev_info['name']}")

    def start_recording(self):
        self.is_recording = True
        self.audio_data = []
        self.stream = self.p.open(format=self.FORMAT,
                                channels=self.CHANNELS,
                                rate=self.RATE,
                                input=True,
                                input_device_index=audio_device_code_input,  # Add input device specification
                                frames_per_buffer=self.CHUNK)
        self.recording_thread = threading.Thread(target=self._record)
        self.recording_thread.start()

    def stop_recording(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.recording_thread:
            self.recording_thread.join()
            self._convert_to_text()

    def _record(self):
        while self.is_recording:
            data = self.stream.read(self.CHUNK)
            self.audio_data.append(data)

    def _convert_to_text(self):
        if not self.audio_data:
            print("Nenhum áudio gravado")
            return

        # Create WAV data in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.CHANNELS)
            wav_file.setsampwidth(self.p.get_sample_size(self.FORMAT))
            wav_file.setframerate(self.RATE)
            wav_file.writeframes(b''.join(self.audio_data))

        # Send audio data to STT server
        try:
            response = requests.post(
                'http://localhost:5502/transcribe',
                data=wav_buffer.getvalue(),
                headers={'Content-Type': 'audio/wav'}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result['success']:
                    texto = result['text']
                    print(f"{Fore.LIGHTBLUE_EX}Você disse: {texto}{Style.RESET_ALL}")
                    
                    # Enviar texto para a API do oobabooga
                    try:
                        headers = {
                            "Content-Type": "application/json"
                        }

                        history.append({"role": "user", "content": texto + commom_instuction})
                        data = {
                            "messages": history,
                            "mode": "instruct",
                            "model": "Meta8BQ4",
                        }
                                    
                        response = requests.post(self.api_url, headers=headers, json=data)
                        
                        if response.status_code == 200:
                            api_response = response.json()
                            assistant_message = api_response['choices'][0]['message']['content']
                            print(f"{Fore.LIGHTRED_EX}Resposta da IA: {assistant_message}{Style.RESET_ALL}\n")
                            history.append({"role": "assistant", "content": assistant_message})
                            # Sintetizar e reproduzir a resposta
                            self._speak_response(assistant_message)
                        else:
                            print(f"Erro na API: Status {response.status_code}")
                            print(f"Detalhes do erro: {response.text}")
                            
                    except Exception as e:
                        print(f"Erro ao comunicar com a API: {e}")
                        print(f"Tipo do erro: {type(e)}")
                    
            else:
                print(f"Erro no servidor STT: {response.status_code}")
                
        except Exception as e:
            print(f"Erro ao comunicar com servidor STT: {e}")

    def _speak_response(self, text):
        try:
            # Send request to TTS server
            response = requests.post(
                self.tts_server_url,
                json={"text": text},
                stream=True
            )
            
            if response.status_code == 200:
                # Create temporary file to store the audio
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            temp_file.write(chunk)
                    temp_file_path = temp_file.name

                # Play the audio
                wf = wave.open(temp_file_path, 'rb')
                stream = self.p.open(
                    format=self.p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True,
                    output_device_index=self.output_device_index
                )
                
                data = wf.readframes(self.CHUNK)
                while data:
                    stream.write(data)
                    data = wf.readframes(self.CHUNK)
                
                stream.stop_stream()
                stream.close()
                wf.close()
                
                # Clean up temporary file
                os.unlink(temp_file_path)
            else:
                print(f"Error from TTS server: {response.status_code}")
                
        except Exception as e:
            print(f"Error in speech synthesis: {e}")

    def __del__(self):
        if self.p:
            self.p.terminate()

def main():
    recorder = VoiceRecorder()
    
    def on_press(key):
        if hasattr(key, 'vk') and key.vk == 96:  # 96 é o código virtual key do '0' do teclado numérico
            if not recorder.is_recording:
                recorder.start_recording()

    def on_release(key):
        if key == keyboard.Key.esc:
            return False
        if hasattr(key, 'vk') and key.vk == 96:  # 96 é o código virtual key do '0' do teclado numérico
            if recorder.is_recording:
                recorder.stop_recording()

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

if __name__ == "__main__":
    main()