from colorama import init, Fore, Style
from pynput import keyboard
import threading
import io
import wave
import pyaudio
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
import time
import uuid  # Add at top of file with other imports
from TTS.api import TTS
from config.settings import (API_CONFIG, AUDIO_DEVICE_INPUT, AUDIO_DEVICE_OUTPUT, 
                           TTS_SERVER_URL, STT_SERVER_URL, TTS_SYNTHESIS_URL, 
                           STT_TRANSCRIBE_URL, COMMON_INSTRUCTION, TIME_CHECK,
                            STT_CONFIG,TTS_CONFIG, MEMORY_CONFIG)
from time import perf_counter
import matplotlib.pyplot as plt
import os
from datetime import datetime
from core.async_server_connection import AsyncServerConnection
import asyncio
import aiohttp
from core.memory_manager import MemoryManager
from core.mother_brain_server import MotherBrain  # Add this import

history = []

def cronometrar(func):
    def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = func(*args, **kwargs)
        end_time = perf_counter()
        elapsed_time = end_time - start_time
        print(f"Tempo transcorrido para {func.__name__}: {elapsed_time:.4f} segundos")
        return result
    return wrapper

def async_cronometrar(func):
    async def wrapper(*args, **kwargs):
        start_time = perf_counter()
        result = await func(*args, **kwargs)
        end_time = perf_counter()
        elapsed_time = end_time - start_time
        print(f"Tempo transcorrido para {func.__name__}: {elapsed_time:.4f} segundos")
        return result
    return wrapper

class PerformanceMetrics:
    def __init__(self):
        self.recording_time = 0
        self.stt_time = 0
        self.ai_time = 0
        self.tts_time = 0
        self.memory_time = 0  # Add memory timing
        self.model_info = {
            'stt_model': STT_CONFIG["engine"] + " - " + STT_CONFIG["whisper"]["model"] if STT_CONFIG["engine"] == "whisper" else STT_CONFIG["engine"], 
            'ai_model': 'GPT-3.5' if API_CONFIG["api_type"] == "openai" else API_CONFIG.get('local_api', {}).get('model', 'Unknown'),
            'tts_model': TTS_CONFIG["engine"],
            'memory_mode': MEMORY_CONFIG["method"]
        }
    
    def report(self):
        return f"""Performance Metrics:
        🧠 Memory Time: {self.memory_time:.2f}s
        🗣️ STT Time: {self.stt_time:.2f}s
        🤖 AI Response Time: {self.ai_time:.2f}s
        🔊 TTS Time: {self.tts_time:.2f}s
        ⌚ Total Time: {(self.memory_time + self.stt_time + self.ai_time + self.tts_time):.2f}s
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

class MainLoop:
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
        
        # Create new event loop for this instance
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.output_device_index = AUDIO_DEVICE_OUTPUT
        self.api_config = API_CONFIG
        self.api_url = self.api_config["local_api"]["url"] if self.api_config["api_type"] == "local" else self.api_config["openai_api"]["url"]
        
        # Initialize server connections
        self.tts_server = AsyncServerConnection(TTS_SERVER_URL, "TTS")
        self.stt_server = AsyncServerConnection(STT_SERVER_URL, "STT")
        
        # Initialize connections using asyncio
        asyncio.run(self.initialize_connections())
        
        self.metrics = PerformanceMetrics()
        
        # Initialize memory system based on config
        if MEMORY_CONFIG["method"] == "redis":
            try:
                self.memory_system = MotherBrain()
                asyncio.run(self.memory_system.initialize())
                print(f"{Fore.GREEN}Redis memory system initialized{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.YELLOW}Failed to initialize Redis memory, falling back to simple memory: {e}{Style.RESET_ALL}")
                self.memory_system = MemoryManager()
        else:
            self.memory_system = MemoryManager()

        self.memory_lock = asyncio.Lock()  # Add lock for memory operations
        print(f"{Fore.GREEN}Memory system initialized in {MEMORY_CONFIG['method']} mode{Style.RESET_ALL}")

        print(f"{Fore.GREEN}Sistema inicializado com modo de memória: {MEMORY_CONFIG['method']}{Style.RESET_ALL}")

        print(f"{Fore.GREEN}Sistema inicializado com sucesso!{Style.RESET_ALL}")
        print("Pressione e segure '0' para gravar, solte para converter para texto.")
        print("Pressione 'ESC' para sair.\n")

    async def initialize_connections(self):
        """Initialize all server connections asynchronously"""
        await asyncio.gather(
            self.tts_server.initialize(),
            self.stt_server.initialize()
        )
        
        await asyncio.gather(
            self.tts_server.wait_for_connection(),
            self.stt_server.wait_for_connection()
        )

    def run_async(self, coro):
        """Helper method to run coroutines in the instance's event loop"""
        return self.loop.run_until_complete(coro)

    async def monitor_connections(self):
        """Async connection monitoring"""
        while True:
            tasks = [
                self.check_server_connection(self.tts_server),
                self.check_server_connection(self.stt_server)
            ]
            await asyncio.gather(*tasks)
            await asyncio.sleep(5)

    async def check_server_connection(self, server):
        """Check single server connection"""
        if not await server.check_connection():
            print(f"Conexão perdida com servidor {server.name}. Tentando reconectar...")
            await server.wait_for_connection()

    async def quick_answer_loop(self):
        recorded_sound = await self.stop_recording()
        transcription = await self.send_audio_to_STT(recorded_sound)
        await self.process_ai_response(transcription)
        
    def start_recording(self):
        print(f"{Fore.CYAN}Iniciando gravação...{Style.RESET_ALL}")
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

    async def stop_recording(self):
        """Async version of stop_recording"""
        print(f"{Fore.CYAN}Parando gravação...{Style.RESET_ALL}")
        self.is_recording = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.recording_thread:
            self.recording_thread.join()
        
        if not self.audio_data:
            print("Nenhum áudio gravado")
            return None

        wav_buffer = None
        try:
            # Create WAV data in memory
            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(self.CHANNELS)
                wav_file.setsampwidth(self.p.get_sample_size(self.FORMAT))
                wav_file.setframerate(self.RATE)
                wav_file.writeframes(b''.join(self.audio_data))
            
            # Important: Reset buffer position
            wav_buffer.seek(0)
            return wav_buffer
            
        except Exception as e:
            print(f"{Fore.RED}Erro ao processar áudio: {str(e)}{Style.RESET_ALL}")
            if wav_buffer:
                wav_buffer.close()
            return None

    async def send_audio_to_STT(self, wav_buffer) -> None:
        """Send audio data to STT server with retry logic"""
        if not wav_buffer:
            return

        if TIME_CHECK:
            stt_start = perf_counter()

        max_retries = 3
        retry_delay = 1

        try:
            headers = {
                'Content-Type': 'audio/wav',
                'X-Session-ID': self.stt_server.session_id,
                'Accept-Encoding': 'gzip, deflate'
            }
            
            # Importante: Crie uma cópia dos dados do buffer
            audio_data = wav_buffer.getvalue()
            
            for attempt in range(max_retries):
                try:
                    async with aiohttp.ClientSession() as session:  # Criar nova sessão para cada tentativa
                        async with session.post(
                            f"{STT_SERVER_URL}/transcribe",
                            data=audio_data,  # Usar a cópia dos dados
                            headers=headers,
                            timeout=aiohttp.ClientTimeout(total=30)
                        ) as response:
                            if response.status == 200:
                                result = await response.json()
                                if result.get("success"):
                                    transcription = result.get("text", "").strip()
                                    print(f"{Fore.LIGHTBLUE_EX}Você disse: {transcription}{Style.RESET_ALL}")
                                    
                                    if TIME_CHECK:
                                        self.metrics.stt_time = perf_counter() - stt_start
                                        
                                    if "model" in result:
                                        self.metrics.model_info['stt_model'] = f"Whisper {result['model']}"
                                        
                                    return transcription if transcription else None
                                
                                print(f"{Fore.RED}Falha na transcrição: {result.get('error')}{Style.RESET_ALL}")
                                return None

                            if response.status in {429} or 500 <= response.status < 600:
                                if attempt < max_retries - 1:
                                    wait_time = retry_delay * (attempt + 1)
                                    print(f"{Fore.YELLOW}Tentativa {attempt + 1} falhou, aguardando {wait_time}s...{Style.RESET_ALL}")
                                    await asyncio.sleep(wait_time)
                                    continue
                                
                            error_text = await response.text()
                            print(f"{Fore.RED}Erro na requisição STT (Status {response.status}): {error_text}{Style.RESET_ALL}")
                            return None

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        print(f"{Fore.YELLOW}Erro de conexão na tentativa {attempt + 1}: {str(e)}, aguardando {wait_time}s...{Style.RESET_ALL}")
                        await asyncio.sleep(wait_time)
                        continue
                    print(f"{Fore.RED}Todas as tentativas falharam. Último erro: {str(e)}{Style.RESET_ALL}")
                    return None

        except Exception as e:
            print(f"{Fore.RED}Erro ao processar áudio: {str(e)}{Style.RESET_ALL}")
            return None
        finally:
            if wav_buffer:
                wav_buffer.close()

    def _record(self):
        while self.is_recording:
            data = self.stream.read(self.CHUNK)
            self.audio_data.append(data)

    async def _speak_response(self, text):
        """Non-blocking speech synthesis"""
        if TIME_CHECK:
            tts_start = perf_counter()
            
        if not self.tts_server.is_connected:
            print(f"{Fore.RED}Servidor TTS não está disponível{Style.RESET_ALL}")
            return

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    TTS_SYNTHESIS_URL,
                    json={"text": text},
                    timeout=aiohttp.ClientTimeout(total=100)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        if TIME_CHECK:
                            self.metrics.tts_time = perf_counter() - tts_start
                        if not result.get("success"):
                            print(f"{Fore.RED}Erro na síntese de voz: {result.get('error')}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}Erro do servidor TTS: {response.status}{Style.RESET_ALL}")
                        response_text = await response.text()
                        print(f"Response: {response_text}")
        except Exception as e:
            print(f"{Fore.RED}Erro na síntese de voz: {str(e)}{Style.RESET_ALL}")

    async def process_ai_response(self, prompt_text):
        if not prompt_text:
            print(f"{Fore.YELLOW}No text to process{Style.RESET_ALL}")
            return

        try:
            if TIME_CHECK:
                ai_start = perf_counter()
                memory_start = perf_counter()

            # Get memory and personality context
            memory_context = ""
            personality_data = None
            async with self.memory_lock:
                try:
                    # Fazer chamadas paralelas para memória e personalidade
                    responses = await asyncio.gather(
                        self.memory_system.get_relevant_context_async(prompt_text),
                        self.memory_system.get_personality()
                    )
                    memory_context = responses[0]
                    personality_data = responses[1]
                except Exception as e:
                    print(f"{Fore.YELLOW}Context retrieval error: {e}{Style.RESET_ALL}")

            # Format the enhanced prompt with actual context
            enhanced_prompt = COMMON_INSTRUCTION.format(
                personality_context=personality_data.get('personality_context', 'Sem dados de personalidade disponíveis') if personality_data else '',
                mood_context=personality_data.get('mood_context', 'Sem dados de humor disponíveis') if personality_data else ''
            )
            enhanced_prompt += f"\nPrevious context: {memory_context}\nCurrent input: {prompt_text}"

            # Debug print for enhanced prompt
            print(f"{Fore.MAGENTA}Enhanced prompt: {enhanced_prompt}{Style.RESET_ALL}")

            # AI request with enhanced prompt
            async with aiohttp.ClientSession() as session:
                headers = {"Content-Type": "application/json"}
                if self.api_config["api_type"] == "openai":
                    headers["Authorization"] = f"Bearer {self.api_config['openai_api']['api_key']}"

                data = {
                    "messages": [{"role": "user", "content": enhanced_prompt}],
                    "model": self.api_config["openai_api"]["model"] if self.api_config["api_type"] == "openai" else self.api_config["local_api"]["model"],
                }

                # Run AI request and speech synthesis concurrently
                async with session.post(
                    self.api_url,
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        ai_response = result["choices"][0]["message"]["content"]
                        
                        if TIME_CHECK:
                            self.metrics.ai_time = perf_counter() - ai_start
                            
                        print(f"{Fore.LIGHTRED_EX}Resposta da AI: {ai_response}{Style.RESET_ALL}")
                        
                        # Store memory and generate speech concurrently, plus analyze interaction
                        await asyncio.gather(
                            self.memory_system.add_dialog_memory_async(prompt_text, ai_response),
                            self._speak_response(ai_response),
                            self.memory_system.analyze_interaction(prompt_text, ai_response)
                        )
                        
                        if TIME_CHECK:
                            print(f"\n{Fore.YELLOW}{self.metrics.report()}{Style.RESET_ALL}")
                            metrics_data = self.metrics.get_metrics_dict()
                            chart_file = await generate_performance_chart_async(metrics_data)
                            print(f"{Fore.GREEN}Performance chart saved as: {chart_file}{Style.RESET_ALL}")
                    else:
                        print(f"Erro no prompt da AI: {response.status}")
        except Exception as e:
            print(f"{Fore.RED}Error in AI response processing: {str(e)}{Style.RESET_ALL}")
            logger.error(f"AI response error: {str(e)}", exc_info=True)

    async def _store_memory(self, prompt_text, ai_response):
        """Asynchronous memory storage with timeout"""
        try:
            async with self.memory_lock:
                await asyncio.wait_for(
                    self.memory_system.add_dialog_memory_async(prompt_text, ai_response),
                    timeout=0.1
                )
        except asyncio.TimeoutError:
            print(f"{Fore.YELLOW}Memory storage timed out{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.YELLOW}Memory storage error: {e}{Style.RESET_ALL}")

    def cleanup(self):
        print("\nFinalizando conexões...")
        self.run_async(self._async_cleanup())
        self.loop.close()
        if hasattr(self, '_session'):
            self.run_async(self._session.close())

    async def _async_cleanup(self):
        """Enhanced cleanup with memory system"""
        cleanup_tasks = [
            self.tts_server.disconnect(),
            self.stt_server.disconnect()
        ]
        
        if hasattr(self.memory_system, 'cleanup'):
            cleanup_tasks.append(self.memory_system.cleanup())
            
        await asyncio.gather(*cleanup_tasks)

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

async def generate_performance_chart_async(metrics_data):
    """Asynchronous version of chart generation"""
    def create_chart():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = 'performance_charts'
        os.makedirs(output_dir, exist_ok=True)
        chart_filename = os.path.join(output_dir, f'performance_metrics_{timestamp}.jpg')
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

    # Run chart generation in thread pool to avoid blocking
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, create_chart)

def main():
    recorder = MainLoop()
    
    def on_press(key):
        if hasattr(key, 'vk') and key.vk == 96:  # 96 é o código virtual key do '0' do teclado numérico
            if not recorder.is_recording:
                recorder.start_recording()

    async def on_release(key):
        if key == keyboard.Key.esc:
            recorder.cleanup()  # Adicionar cleanup antes de sair
            return False
        if hasattr(key, 'vk') and key.vk == 96:  # 96 é o código virtual key do '0' do teclado numérico
            if recorder.is_recording:
                await recorder.quick_answer_loop()

    try:
        with keyboard.Listener(
            on_press=on_press, 
            on_release=lambda key: recorder.run_async(on_release(key))
        ) as listener:
            listener.join()
    except Exception as e:
        print(f"Error in main loop: {e}")
    finally:
        recorder.cleanup()

if __name__ == "__main__":
    main()