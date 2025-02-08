import threading
import requests
import time
import uuid
from colorama import Fore, Style
import logging

class ServerConnection:
    def __init__(self, url, name):
        self.url = url.rstrip('/')
        self.name = name
        self.session_id = str(uuid.uuid4())
        self.is_connected = False
        self.logger = logging.getLogger(__name__)
        self._max_retries = 10
        self._retry_delay = 2
        print(f"Iniciando {name} com session_id: {self.session_id}")

    def check_connection(self):
        """Verifica se a conexão está ativa"""
        try:
            if self.name == "Audio":
                response = requests.get(f"{self.url}/health?session_id={self.session_id}", timeout=2)
            else:
                response = requests.get(
                    f"{self.url}/health",
                    headers={'X-Session-ID': self.session_id},
                    timeout=2
                )
            self.is_connected = response.status_code == 200
            return self.is_connected
        except:
            self.is_connected = False
            return False

    def wait_for_connection(self):
        """Tenta estabelecer conexão com retry"""
        print(f"{Fore.YELLOW}Conectando ao servidor {self.name}...{Style.RESET_ALL}")
        
        for attempt in range(self._max_retries):
            try:
                if self.name == "Audio":
                    # Audio server usa endpoint root com session_id na URL
                    response = requests.get(f"{self.url}/?session_id={self.session_id}")
                else:
                    # Outros servidores usam endpoint connect com header
                    response = requests.post(
                        f"{self.url}/connect",
                        headers={'X-Session-ID': self.session_id},
                        timeout=5
                    )

                if response.status_code == 200:
                    self.is_connected = True
                    print(f"{Fore.GREEN}Conectado ao servidor {self.name}{Style.RESET_ALL}")
                    return True
                    
            except requests.exceptions.RequestException as e:
                print(f"{Fore.RED}Tentativa {attempt + 1} falhou para {self.name}: {str(e)}{Style.RESET_ALL}")
                
            if attempt < self._max_retries - 1:
                time.sleep(self._retry_delay)
                
        self.is_connected = False
        raise ConnectionError(f"Não foi possível conectar ao servidor {self.name}")

    def disconnect(self):
        """Desconecta do servidor"""
        if not self.is_connected:
            return

        try:
            if self.name == "Audio":
                # Audio server não precisa de disconnect explícito
                pass
            else:
                requests.post(
                    f"{self.url}/disconnect",
                    headers={'X-Session-ID': self.session_id},
                    timeout=2
                )
        except:
            pass
        finally:
            self.is_connected = False
