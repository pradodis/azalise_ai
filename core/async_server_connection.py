import asyncio
import aiohttp
from colorama import Fore, Style
import uuid
import logging
from typing import Optional

class AsyncServerConnection:
    def __init__(self, url: str, name: str):
        self.url = url.rstrip('/')
        self.name = name
        self.session_id = str(uuid.uuid4())
        self.is_connected = False
        self.session: Optional[aiohttp.ClientSession] = None
        self._max_retries = 10
        self._retry_delay = 2
        print(f"Iniciando {name} com session_id: {self.session_id}")

    async def initialize(self):
        """Initialize aiohttp session"""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            self.session = None

    async def check_connection(self) -> bool:
        """Check if connection is active"""
        if not self.session:
            await self.initialize()
        
        try:
            # Use root endpoint for all initial checks
            endpoint = "/"
            params = {"session_id": self.session_id} if self.name == "Audio" else None
            headers = {'X-Session-ID': self.session_id} if self.name != "Audio" else None
            
            print(f"{Fore.YELLOW}Verificando conexão com {self.name} em {self.url}{endpoint}{Style.RESET_ALL}")
            
            async with self.session.get(
                f"{self.url}{endpoint}",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as response:
                self.is_connected = response.status == 200
                
                if self.is_connected:
                    print(f"{Fore.GREEN}✓ Conectado ao servidor {self.name}{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}✗ Falha ao conectar ao servidor {self.name} (Status: {response.status}){Style.RESET_ALL}")
                    try:
                        error_text = await response.text()
                        print(f"{Fore.RED}Resposta do servidor: {error_text}{Style.RESET_ALL}")
                    except:
                        pass
                
                return self.is_connected
                
        except Exception as e:
            print(f"{Fore.RED}Erro ao verificar conexão com {self.name}: {str(e)}{Style.RESET_ALL}")
            self.is_connected = False
            return False

    async def connect(self) -> bool:
        """Establish connection and register session"""
        if not self.session:
            await self.initialize()
            
        try:
            if self.name == "Audio":
                # Audio server uses root endpoint with query parameter
                response = await self.session.get(
                    f"{self.url}/?session_id={self.session_id}",
                    timeout=aiohttp.ClientTimeout(total=5)
                )
            else:
                # STT and TTS servers use root endpoint with header
                response = await self.session.get(
                    f"{self.url}/",
                    headers={'X-Session-ID': self.session_id},
                    timeout=aiohttp.ClientTimeout(total=5)
                )
                
            if response.status == 200:
                self.is_connected = True
                print(f"{Fore.GREEN}✓ Registrado no servidor {self.name}{Style.RESET_ALL}")
                return True
                
            print(f"{Fore.RED}✗ Falha ao registrar no servidor {self.name} (Status: {response.status}){Style.RESET_ALL}")
            try:
                error_text = await response.text()
                print(f"{Fore.RED}Resposta do servidor: {error_text}{Style.RESET_ALL}")
            except:
                pass
            return False
            
        except Exception as e:
            print(f"{Fore.RED}Erro ao conectar com {self.name}: {str(e)}{Style.RESET_ALL}")
            return False

    async def wait_for_connection(self):
        """Try to establish connection with retry"""
        print(f"{Fore.YELLOW}Conectando ao servidor {self.name}...{Style.RESET_ALL}")
        
        for attempt in range(self._max_retries):
            try:
                if await self.connect():
                    return True
                    
                print(f"{Fore.YELLOW}Tentativa {attempt + 1} falhou, tentando novamente em {self._retry_delay}s...{Style.RESET_ALL}")
                
            except Exception as e:
                print(f"{Fore.RED}Erro na tentativa {attempt + 1} para {self.name}: {str(e)}{Style.RESET_ALL}")
                
            if attempt < self._max_retries - 1:
                await asyncio.sleep(self._retry_delay)
                
        self.is_connected = False
        raise ConnectionError(f"Não foi possível conectar ao servidor {self.name} após {self._max_retries} tentativas")

    async def disconnect(self):
        """Disconnect from server"""
        if not self.is_connected:
            return

        try:
            if self.name == "Audio":
                # Audio server doesn't need explicit disconnect
                pass
            else:
                async with self.session.post(
                    f"{self.url}/disconnect",
                    headers={'X-Session-ID': self.session_id},
                    timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    if response.status == 200:
                        print(f"Desconectado do servidor {self.name}")
        except:
            pass
        finally:
            self.is_connected = False
            await self.close()
