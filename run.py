from colorama import init, Fore, Style
from pynput import keyboard
import threading
import io
import wave
import pyaudio
import requests
import time
import uuid  # Add at top of file with other imports
from TTS.api import TTS
from config.settings import (API_CONFIG, AUDIO_DEVICE_INPUT, AUDIO_DEVICE_OUTPUT, 
                           TTS_SERVER_URL, STT_SERVER_URL, TTS_SYNTHESIS_URL, 
                           STT_TRANSCRIBE_URL, COMMON_INSTRUCTION, TIME_CHECK,
                            STT_CONFIG,TTS_CONFIG, AUDIO_SERVER_URL)
from time import perf_counter
import matplotlib.pyplot as plt
import os
from datetime import datetime

history = []

class PerformanceMetrics:
    def __init__(self):
        self.recording_time = 0
        self.stt_time = 0
        self.ai_time = 0
        self.tts_time = 0
        self.model_info = {
            'stt_model': STT_CONFIG["engine"] + " - " + STT_CONFIG["whisper"]["model"] if STT_CONFIG["engine"] == "whisper" else STT_CONFIG["engine"], 
            'ai_model': 'GPT-3.5' if API_CONFIG["api_type"] == "openai" else API_CONFIG.get('local_api', {}).get('model', 'Unknown'),
            'tts_model': TTS_CONFIG["engine"]
        }
    
    def report(self):
        return f"""Performance Metrics:
        🗣️ STT Time: {self.stt_time:.2f}s
        🤖 AI Response Time: {self.ai_time:.2f}s
        🔊 TTS Time: {self.tts_time:.2f}s
        ⌚ Total Time: {(self.stt_time + self.ai_time + self.tts_time):.2f}s
        """
    
    def get_metrics_dict(self):
        return {
            'stt_time': self.stt_time,
            'ai_time': self.ai_time,
            'tts_time': self.tts_time,
            'total_time': self.stt_time + self.ai_time + self.tts_time,
            'models': self.model_info
        }

class ServerConnection:
    def __init__(self, url, name):
        self.url = url
        self.name = name
        self.is_connected = False
        self.last_state = False
        self.lock = threading.Lock()
        self.session_id = str(uuid.uuid4())
        print(f"Iniciando {name} com session_id: {self.session_id}")
        
    def check_connection(self):
        try:
            # Adicionar logs para debug
            response = requests.get(f"{self.url}?session_id={self.session_id}")
            
            with self.lock:
                self.last_state = self.is_connected
                self.is_connected = response.status_code == 200
                
                if self.is_connected and not self.last_state:
                    print(f"{Fore.GREEN}✓ Cliente conectado ao servidor {self.name} (Session: {self.session_id}){Style.RESET_ALL}")
                elif not self.is_connected and self.last_state:
                    print(f"{Fore.RED}✗ Cliente desconectado do servidor {self.name} (Session: {self.session_id}){Style.RESET_ALL}")
                    
            return self.is_connected
        except Exception as e:
            print(f"Erro ao verificar conexão com {self.name}: {str(e)}")
            with self.lock:
                if self.is_connected:  # Only show message on state change
                    print(f"{Fore.RED}✗ Cliente desconectado do servidor {self.name}{Style.RESET_ALL}")
                self.last_state = self.is_connected
                self.is_connected = False
            return False

    def wait_for_connection(self):
        while not self.is_connected:
            print(f"Tentando conectar ao servidor {self.name}...")
            if self.check_connection():
                print(f"Conectado ao servidor {self.name}!")
                break
            time.sleep(5)

    def disconnect(self):
        try:
            if self.is_connected:
                response = requests.post(
                    f"{self.url}/disconnect",
                    headers={'X-Session-ID': self.session_id}
                )
                if response.status_code == 200:
                    print(f"Desconectado do servidor {self.name}")
                self.is_connected = False
        except Exception as e:
            print(f"Erro ao desconectar do servidor {self.name}: {str(e)}")

class VoiceRecorder:
    def __init__(self):
        init()
        self.is_recording = False
        self.audio_data = []
        self.recording_thread = None
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 44100
        
        self.output_device_index = AUDIO_DEVICE_OUTPUT
        self.api_config = API_CONFIG
        self.api_url = self.api_config["local_api"]["url"] if self.api_config["api_type"] == "local" else self.api_config["openai_api"]["url"]
        
        # Initialize server connections
        self.tts_server = ServerConnection(TTS_SERVER_URL, "TTS")
        self.stt_server = ServerConnection(STT_SERVER_URL, "STT")
        self.audio_server = ServerConnection(AUDIO_SERVER_URL, "AUDIO")
        
        # Start connection monitoring threads
        self.start_connection_monitors()
        
        # Wait for initial connections
        self.tts_server.wait_for_connection()
        self.stt_server.wait_for_connection()
        self.audio_server.wait_for_connection()

        self.metrics = PerformanceMetrics()

        print("Sistema inicializado com sucesso!")
        print("Pressione e segure '0' para gravar, solte para converter para texto.")
        print("Pressione 'ESC' para sair.\n")

    def start_connection_monitors(self):
        def monitor_connection(server):
            while True:
                if not server.check_connection():
                    print(f"Conexão perdida com servidor {server.name}. Tentando reconectar...")
                    server.wait_for_connection()
                time.sleep(5)

        threading.Thread(target=monitor_connection, args=(self.tts_server,), daemon=True).start()
        threading.Thread(target=monitor_connection, args=(self.stt_server,), daemon=True).start()
        threading.Thread(target=monitor_connection, args=(self.audio_server,), daemon=True).start()

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
        if TIME_CHECK:
            self.record_start_time = perf_counter()
        self.is_recording = True
        self.audio_data = []
        self.stream = self.p.open(format=self.FORMAT,
                                channels=self.CHANNELS,
                                rate=self.RATE,
                                input=True,
                                input_device_index=AUDIO_DEVICE_INPUT,
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
            if TIME_CHECK:
                self.metrics.recording_time = perf_counter() - self.record_start_time
            self._convert_to_text()

    def _record(self):
        while self.is_recording:
            data = self.stream.read(self.CHUNK)
            self.audio_data.append(data)

    def _convert_to_text(self):
        if not self.audio_data:
            print("Nenhum áudio gravado")
            return

        if not self.stt_server.is_connected:
            print("Servidor STT não está disponível")
            return

        # STT timing
        if TIME_CHECK:
            stt_start = perf_counter()

        # Create WAV data in memory
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.CHANNELS)
            wav_file.setsampwidth(self.p.get_sample_size(self.FORMAT))
            wav_file.setframerate(self.RATE)
            wav_file.writeframes(b''.join(self.audio_data))

        # Send audio data to STT server with session ID
        try:
            headers = {
                'Content-Type': 'audio/wav',
                'X-Session-ID': self.stt_server.session_id  # Garantir que o session_id está sendo enviado
            }
            
            response = requests.post(
                STT_TRANSCRIBE_URL,
                data=wav_buffer.getvalue(),
                headers=headers
            )
            
            if response.status_code == 200:
                if TIME_CHECK:
                    ai_start = perf_counter()
                result = response.json()
                if result['success']:
                    texto = result['text']
                    # Update Whisper model information if available in response
                    if 'model' in result:
                        self.metrics.model_info['stt_model'] = f"Whisper {result['model']}"
                    print(f"{Fore.LIGHTBLUE_EX}Você disse: {texto}{Style.RESET_ALL}")
                    
                    # Enviar texto para a API do oobabooga
                    try:
                        headers = {
                            "Content-Type": "application/json"
                        }

                        history.append({"role": "user", "content": texto + COMMON_INSTRUCTION})
                        
                        if self.api_config["api_type"] == "local":
                            data = {
                                "messages": history,
                                "mode": "instruct",
                                "model": self.api_config["local_api"]["model"],
                            }
                        else:
                            headers["Authorization"] = f"Bearer {self.api_config['openai_api']['api_key']}"
                            data = {
                                "messages": history,
                                "model": self.api_config["openai_api"]["model"],
                                "temperature": 0.7
                            }
                                    
                        response = requests.post(self.api_url, headers=headers, json=data)
                        
                        if response.status_code == 200:
                            if TIME_CHECK:
                                self.metrics.ai_time = perf_counter() - ai_start
                                self.metrics.stt_time = ai_start - stt_start
                            api_response = response.json()
                            
                            # Update AI model information for OpenAI
                            if self.api_config["api_type"] == "openai" and "model" in api_response:
                                self.metrics.model_info['ai_model'] = api_response["model"]
                            
                            assistant_message = api_response['choices'][0]['message']['content']
                            print(f"{Fore.LIGHTRED_EX}Resposta da IA: {assistant_message}{Style.RESET_ALL}\n")
                            history.append({"role": "assistant", "content": assistant_message})
                            # Sintetizar e reproduzir a resposta
                            self._speak_response(assistant_message)
                            if TIME_CHECK:
                                print(f"\n{Fore.YELLOW}{self.metrics.report()}{Style.RESET_ALL}")
                                # Generate and save the chart
                                metrics_data = self.metrics.get_metrics_dict()
                                chart_file = generate_performance_chart(metrics_data)
                                print(f"{Fore.GREEN}Performance chart saved as: {chart_file}{Style.RESET_ALL}")
                        else:
                            print(f"Erro na API: Status {response.status_code}")
                            print(f"Detalhes do erro: {response.text}")
                            
                    except Exception as e:
                        print(f"Erro ao comunicar com a API: {e}")
                        print(f"Tipo do erro: {type(e)}")
                    
            elif response.status_code == 403:
                print(f"{Fore.RED}Erro de autenticação com o servidor STT. Session ID: {self.stt_server.session_id}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}Erro no servidor STT: {response.status_code}{Style.RESET_ALL}")
                
        except Exception as e:
            print(f"Erro ao comunicar com servidor STT: {e}")


    def _send_to_audio_server(self, file_path, priority=1):
        """Send audio file to audio server asynchronously"""
        def delete_file_with_retry(file_path, max_retries=3, delay=0.5):
            """Helper function to retry file deletion"""
            for attempt in range(max_retries):
                try:
                    if os.path.exists(file_path):
                        os.unlink(file_path)
                        return True
                except PermissionError:
                    if attempt < max_retries - 1:
                        time.sleep(delay)
                        continue
                    return False
            return False
        def send_request():
            try:
                data = {
                    "file_path": file_path,
                    "priority": priority,
                    "delete_after": True  # Let audio server handle file deletion
                }
                response = requests.post(
                    f"{self.audio_server.url}/play", 
                    json=data,
                    headers={'X-Session-ID': self.audio_server.session_id}
                )
                if response.status_code == 200:
                    print("Audio sent to server successfully")
                else:
                    print(f"Error sending audio to server: {response.status_code}")
                    # Only attempt deletion if audio server failed
                    if not delete_file_with_retry(file_path):
                        print(f"Warning: Could not delete temporary file: {file_path}")
            except Exception as e:
                print(f"Error in send_request: {e}")
                if not delete_file_with_retry(file_path):
                    print(f"Warning: Could not delete temporary file: {file_path}")
        
        # Start async thread to send audio
        threading.Thread(target=send_request, daemon=True).start()

    def _speak_response(self, text):
        if TIME_CHECK:
            tts_start = perf_counter()
        if not self.tts_server.is_connected:
            print("Servidor TTS não está disponível")
            return

        try:
            # Send request to TTS server
            response = requests.post(
                TTS_SYNTHESIS_URL,
                json={"text": text}
            )
            
            if response.status_code == 200:
                # Get synthesized audio file path
                result = response.json()
                audio_file = result.get('file_path')
                if TIME_CHECK:
                    self.metrics.tts_time = perf_counter() - tts_start
                if audio_file:
                    # Send to audio server asynchronously
                    self._send_to_audio_server(audio_file)
            else:
                print(f"Error from TTS server: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"Error in speech synthesis: {e}")

    def cleanup(self):
        print("\nFinalizando conexões...")
        self.tts_server.disconnect()
        self.stt_server.disconnect()
        self.audio_server.disconnect()
        if self.p:
            self.p.terminate()

    def __del__(self):
        self.cleanup()

def save_performance_log(metrics_data, log_filename):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = (
        f"Timestamp: {timestamp}\n"
        f"STT Time ({metrics_data['models']['stt_model']}): {metrics_data['stt_time']:.2f}s\n"
        f"AI Time ({metrics_data['models']['ai_model']}): {metrics_data['ai_time']:.2f}s\n"
        f"TTS Time ({metrics_data['models']['tts_model']}): {metrics_data['tts_time']:.2f}s\n"
        f"Total Time: {metrics_data['total_time']:.2f}s\n"
        f"{'='*50}\n"
    )
    
    with open(log_filename, 'a', encoding='utf-8') as f:
        f.write(log_entry)

def generate_performance_chart(metrics_data):
    # Create data for the chart
    times = [
        metrics_data['stt_time'],
        metrics_data['ai_time'],
        metrics_data['tts_time'],
        metrics_data['total_time']
    ]
    labels = [
        f'STT\n({metrics_data["models"]["stt_model"]})',
        f'AI\n({metrics_data["models"]["ai_model"]})',
        f'TTS\n({metrics_data["models"]["tts_model"]})',
        'Total\nTime'
    ]

    # Create the bar chart with more width for all columns
    plt.figure(figsize=(12, 6))
    bars = plt.bar(labels, times)
    
    # Customize the chart
    plt.title('Performance Metrics by Component')
    plt.ylabel('Time (seconds)')
    plt.ylim(0, metrics_data['total_time'] * 1.1)

    # Color the total time bar differently
    bars[-1].set_color('lightgray')
    
    # Add value labels on top of bars
    for bar in bars:
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.2f}s',
                ha='center', va='bottom')

    # Save the chart
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = 'performance_charts'
    os.makedirs(output_dir, exist_ok=True)
    
    # Save log file
    log_filename = os.path.join(output_dir, 'performance_log.txt')
    save_performance_log(metrics_data, log_filename)
    
    # Save chart
    chart_filename = os.path.join(output_dir, f'performance_metrics_{timestamp}.jpg')
    plt.savefig(chart_filename, dpi=300, bbox_inches='tight')
    plt.close()
    
    return chart_filename

def main():
    recorder = VoiceRecorder()
    
    def on_press(key):
        if hasattr(key, 'vk') and key.vk == 96:  # 96 é o código virtual key do '0' do teclado numérico
            if not recorder.is_recording:
                recorder.start_recording()

    def on_release(key):
        if key == keyboard.Key.esc:
            recorder.cleanup()  # Adicionar cleanup antes de sair
            return False
        if hasattr(key, 'vk') and key.vk == 96:  # 96 é o código virtual key do '0' do teclado numérico
            if recorder.is_recording:
                recorder.stop_recording()

    try:
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            listener.join()
    finally:
        recorder.cleanup()  # Garantir que cleanup seja chamado mesmo em caso de erro

if __name__ == "__main__":
    main()