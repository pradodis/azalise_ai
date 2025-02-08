from flask import Flask, request, jsonify, session
import pygame
import threading
from collections import deque
import time
import os
from datetime import datetime

class AudioConfig:
    """Configurações do sistema de áudio"""
    SAMPLE_RATE = 44100
    CHANNELS = 2
    BUFFER_SIZE = 256  # Reduzido de 512 para 256
    SUPPORTED_FORMATS = ['.wav', '.mp3', '.ogg']
    MAX_QUEUE_SIZE = 100

class AudioServer:
    def __init__(self):
        self.app = Flask(__name__)
        # Disable Flask's default logging
        import logging
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)  # Only show errors
        self.app.logger.disabled = True
        self.app.secret_key = os.urandom(24)  # Para gerenciamento de sessão
        self.active_sessions = set()
        self.audio_queue = deque(maxlen=AudioConfig.MAX_QUEUE_SIZE)
        self.is_playing = False
        self.lock = threading.Lock()
        self.start_time = datetime.now()
        self.stats = {
            'total_played': 0,
            'errors': 0,
            'uptime': 0
        }
        
        self.setup_routes()
        self.init_audio_system()

    def init_audio_system(self):
        """Inicialização otimizada do sistema de áudio"""
        try:
            # Inicializar pygame primeiro
            pygame.init()
            # Criar uma janela oculta para o sistema de vídeo
            pygame.display.set_mode((1, 1), pygame.HIDDEN)
            
            # Inicializar o sistema de áudio
            pygame.mixer.init(
                frequency=AudioConfig.SAMPLE_RATE,
                size=-16,
                channels=AudioConfig.CHANNELS,
                buffer=AudioConfig.BUFFER_SIZE
            )
            print(f"{time.strftime('%H:%M:%S')} [AUDIO] Sistema de áudio inicializado com sucesso")
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} [AUDIO] Erro na inicialização do áudio: {str(e)}")
            raise

    def __del__(self):
        """Cleanup quando o servidor for eliminado"""
        try:
            pygame.mixer.quit()
            pygame.quit()
        except:
            pass

    def setup_routes(self):
        """Configuração das rotas da API"""
        
        @self.app.before_request
        def validate_session():
            """Valida a sessão antes de cada requisição"""
            # Lista de endpoints que não requerem validação de sessão
            public_endpoints = ['connect', 'health_check', 'root']
            
            if request.endpoint in public_endpoints:
                return
                
            session_id = request.headers.get('X-Session-ID')
            if session_id and session_id in self.active_sessions:
                return
                
            # Tenta pegar o session_id dos parâmetros da URL
            session_id = request.args.get('session_id')
            if session_id and session_id in self.active_sessions:
                return
                
            return jsonify({"error": "Invalid or expired session"}), 403

        @self.app.route('/connect', methods=['POST'])
        def connect():
            """Estabelece uma nova conexão com o servidor"""
            session_id = request.headers.get('X-Session-ID')
            if not session_id:
                return jsonify({"error": "No session ID provided"}), 400
            
            self.active_sessions.add(session_id)
            print(f"{time.strftime('%H:%M:%S')} [AUDIO] Cliente conectado (Session: {session_id})")
            
            return jsonify({
                "status": "success",
                "message": "Connected to Audio server",
                "session_id": session_id
            }), 200

        @self.app.route('/disconnect', methods=['POST'])
        def disconnect():
            """Encerra uma conexão existente"""
            session_id = request.headers.get('X-Session-ID')
            if not session_id:
                return jsonify({"error": "No session ID provided"}), 400
                
            if session_id in self.active_sessions:
                self.active_sessions.remove(session_id)
                print(f"{time.strftime('%H:%M:%S')} [AUDIO] Cliente desconectado (Session: {session_id})")
                return jsonify({
                    "status": "success",
                    "message": "Disconnected from Audio server"
                }), 200
            
            return jsonify({"error": "Invalid session ID"}), 403

        @self.app.route('/', methods=['GET'])
        def root():
            """Rota raiz para validação de sessão"""
            session_id = request.args.get('session_id')
            if session_id:
                # Se o session_id for fornecido, adiciona à lista de sessões ativas
                self.active_sessions.add(session_id)
                
            return jsonify({
                "status": "ok",
                "message": "Audio server is running",
                "session_id": session_id if session_id else "not provided"
            }), 200

        @self.app.route('/play', methods=['POST'])
        def play_audio():
            return self.handle_play_request()

        @self.app.route('/stop', methods=['POST'])
        def stop_audio():
            return self.handle_stop_request()

        @self.app.route('/status', methods=['GET'])
        def get_status():
            return self.handle_status_request()
            
        @self.app.route('/health', methods=['GET'])
        def health_check():
            """Health check endpoint"""
            session_id = request.args.get('session_id')
            response = {
                "status": "healthy",
                "server": "Audio Server",
                "uptime": (datetime.now() - self.start_time).total_seconds(),
                "active_sessions": len(self.active_sessions)
            }
            
            if session_id:
                response["session_valid"] = session_id in self.active_sessions
                
            return jsonify(response), 200

    def validate_audio_file(self, file_path):
        """Validação do arquivo de áudio"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
            
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in AudioConfig.SUPPORTED_FORMATS:
            raise ValueError(f"Formato não suportado. Use: {AudioConfig.SUPPORTED_FORMATS}")

    def handle_play_request(self):
        """Manipulação de requisições de reprodução"""
        try:
            data = request.get_json()
            file_path = data.get('file_path')
            priority = data.get('priority', 5)
            delete_after = data.get('delete_after', False)  # New parameter

            if not file_path:
                return jsonify({"error": "Caminho do arquivo não especificado"}), 400

            self.validate_audio_file(file_path)

            with self.lock:
                self.audio_queue.append({
                    'file_path': file_path,
                    'priority': priority,
                    'delete_after': delete_after,  # Store delete_after flag
                    'timestamp': time.time()
                })
                print(f"{time.strftime('%H:%M:%S')} [AUDIO] Áudio adicionado à fila: {file_path}")

            if not self.is_playing:
                threading.Thread(target=self.process_audio_queue, daemon=True).start()

            queue_position = len(self.audio_queue)
            estimated_wait = queue_position * 2  # Estimativa básica

            return jsonify({
                "message": "Áudio adicionado à fila",
                "position": queue_position,
                "estimated_wait_seconds": estimated_wait
            }), 200

        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} [AUDIO] Erro ao processar requisição: {str(e)}")
            self.stats['errors'] += 1
            return jsonify({"error": str(e)}), 500

    def process_audio_queue(self):
        """Processamento otimizado da fila de áudio"""
        while self.audio_queue:
            with self.lock:
                if not self.is_playing:
                    self.is_playing = True
                    audio_info = self.audio_queue.popleft()
                    file_path = audio_info['file_path']
                    delete_after = audio_info.get('delete_after', False)
                    
                    try:
                        start_time = time.time()
                        
                        # Configurar evento de fim de música
                        MUSIC_END = pygame.USEREVENT + 1
                        pygame.mixer.music.set_endevent(MUSIC_END)
                        
                        # Carregar e reproduzir imediatamente
                        pygame.mixer.music.load(file_path)
                        pygame.mixer.music.play()
                        
                        # Esperar o fim da música com timeout reduzido
                        while pygame.mixer.music.get_busy():
                            # Verificar eventos a cada 1ms ao invés de 10ms
                            pygame.time.wait(1)
                            for event in pygame.event.get():
                                if event.type == MUSIC_END:
                                    break
                        
                        duration = time.time() - start_time
                        self.stats['total_played'] += 1
                        print(f"{time.strftime('%H:%M:%S')} [AUDIO] Áudio reproduzido: {file_path} "
                              f"(Duração: {duration:.2f}s)")
                        
                    except Exception as e:
                        print(f"{time.strftime('%H:%M:%S')} [AUDIO] Erro na reprodução: {str(e)}")
                        self.stats['errors'] += 1
                    finally:
                        # Limpeza mais rápida
                        pygame.mixer.music.stop()
                        pygame.mixer.music.unload()
                        
                        if delete_after and os.path.exists(file_path):
                            try:
                                os.unlink(file_path)
                                print(f"{time.strftime('%H:%M:%S')} [AUDIO] Arquivo deletado: {file_path}")
                            except Exception as e:
                                print(f"{time.strftime('%H:%M:%S')} [AUDIO] Erro ao deletar arquivo: {e}")
                        
                        self.is_playing = False

    def handle_health_check(self):
        """Verificação de saúde do sistema"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        session_id = request.args.get('session_id')
        
        if session_id and session_id not in self.active_sessions:
            self.active_sessions.add(session_id)
            #self.logger.info(f"Sessão reconectada via health check: {session_id}")
            
        return jsonify({
            "status": "healthy",
            "uptime_seconds": uptime,
            "stats": self.stats,
            "queue_size": len(self.audio_queue),
            "memory_usage": self.get_memory_usage(),
            "active_sessions": len(self.active_sessions),
            "session_valid": session_id in self.active_sessions if session_id else False
        }), 200

    def get_memory_usage(self):
        """Monitoramento de uso de memória"""
        import psutil
        process = psutil.Process(os.getpid())
        return {
            "memory_mb": process.memory_info().rss / 1024 / 1024,
            "cpu_percent": process.cpu_percent()
        }

    def run(self, host='0.0.0.0', port=5503):
        """Inicialização do servidor"""
        try:
            print(f"{time.strftime('%H:%M:%S')} [AUDIO] Iniciando servidor de áudio em {host}:{port}")
            self.app.run(host=host, port=port, threaded=True)
        except Exception as e:
            print(f"{time.strftime('%H:%M:%S')} [AUDIO] Falha ao iniciar servidor de áudio: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        audio_server = AudioServer()
        audio_server.run()
    except Exception as e:
        print(f"{time.strftime('%H:%M:%S')} [AUDIO] Erro fatal ao iniciar servidor: {str(e)}")