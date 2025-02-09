from colorama import init, Fore, Style
import time
import torch
from TTS.api import TTS
from TTS.utils.manage import ModelManager
import sounddevice as sd
import numpy as np
from datetime import datetime

class TTSSpeedTest:
    def __init__(self):
        init()  # Initialize colorama
        print(f"{Fore.CYAN}Inicializando TTS...{Style.RESET_ALL}")
        
        # Inicializar TTS
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Usando dispositivo: {self.device}")
        
        # Carregar modelo
        model_load_start = time.perf_counter()
        try:
            # Usar ModelManager corretamente
            manager = ModelManager()
            model_name = None
            
            # Procurar por um modelo em português
            for model_type in manager.models_dict:
                if 'pt' in manager.models_dict[model_type]:
                    for dataset in manager.models_dict[model_type]['pt']:
                        models = manager.models_dict[model_type]['pt'][dataset]
                        if models:
                            model_name = f"tts_models/pt/{dataset}/{next(iter(models))}"
                            break
                if model_name:
                    break
            
            if not model_name:
                raise Exception("Nenhum modelo em português encontrado!")
            
            print(f"Usando modelo: {model_name}")
            self.tts = TTS(model_name).to(self.device)
            
            model_load_time = time.perf_counter() - model_load_start
            print(f"{Fore.GREEN}Modelo carregado em {model_load_time:.2f}s{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Erro ao carregar modelo: {str(e)}{Style.RESET_ALL}")
            raise e

    def test_tts_speed(self, text):
        print(f"\n{Fore.CYAN}Testando TTS com texto: '{text}'{Style.RESET_ALL}\n")

        try:
            # Medir tempo de síntese
            synthesis_start = time.perf_counter()
            wav = self.tts.tts(text=text)
            synthesis_end = time.perf_counter()
            synthesis_time = synthesis_end - synthesis_start

            # Medir tempo de preparação para reprodução
            prepare_start = time.perf_counter()
            audio_array = np.array(wav)
            prepare_end = time.perf_counter()
            prepare_time = prepare_end - prepare_start

            # Medir latência antes da reprodução
            latency_start = time.perf_counter()
            sd.play(audio_array, samplerate=22050)
            latency_end = time.perf_counter()
            latency_time = latency_end - latency_start

            # Medir tempo de reprodução
            playback_start = time.perf_counter()
            sd.wait()  # Esperar até terminar a reprodução
            playback_end = time.perf_counter()
            playback_time = playback_end - playback_start
            
            # Tempo total
            total_time = playback_end - synthesis_start
            
            # Imprimir resultados
            print(f"\n{Fore.GREEN}Resultados de Performance Detalhados:{Style.RESET_ALL}")
            print(f"🔄 Síntese: {synthesis_time:.3f}s")
            print(f"⚡ Preparação do array: {prepare_time:.6f}s")
            print(f"⏳ Latência pré-reprodução: {latency_time:.6f}s")
            print(f"🔊 Reprodução: {playback_time:.3f}s")
            print(f"⌚ Tempo Total: {total_time:.3f}s")
            print(f"💻 Dispositivo: {self.device}")
            
        except Exception as e:
            print(f"{Fore.RED}Erro durante o teste: {str(e)}{Style.RESET_ALL}")

def main():
    tester = TTSSpeedTest()
    # Testar com diferentes tamanhos de texto
    texts = [
        "Olá, teste curto.",
        "Esta é uma frase de tamanho médio para teste de velocidade.",
        "Este é um texto mais longo para testarmos a velocidade de síntese. Queremos ver como o modelo se comporta com textos maiores e mais complexos."
    ]
    
    for text in texts:
        print(f"\n{Fore.YELLOW}Testing with text length: {len(text)} characters{Style.RESET_ALL}")
        tester.test_tts_speed(text)
        time.sleep(1)  # Pequena pausa entre os testes

if __name__ == "__main__":
    main()