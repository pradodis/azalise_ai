from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from datetime import datetime
import asyncio
from core.memory_handler import RedisMemoryManager
from config.settings import MEMORY_CONFIG

class BaseMemory(ABC):
    @abstractmethod
    def add_dialog_memory(self, user_text: str, ai_response: str, context: dict = None):
        pass

    @abstractmethod
    def get_relevant_context(self, current_text: str, limit: int = 5) -> str:
        pass

class SimpleMemory(BaseMemory):
    def __init__(self):
        self.conversation_history = []
        self.max_history = 10  # Manter últimas 10 interações

    def add_dialog_memory(self, user_text: str, ai_response: str, context: dict = None):
        self.conversation_history.append({
            "timestamp": datetime.now(),
            "user": user_text,
            "assistant": ai_response
        })
        
        # Manter apenas as últimas N interações
        if len(self.conversation_history) > self.max_history:
            self.conversation_history.pop(0)

    def get_relevant_context(self, current_text: str, limit: int = 5) -> str:
        if not self.conversation_history:
            return ""
            
        context_str = "\nConversa anterior:\n"
        recent_history = self.conversation_history[-limit:]
        
        for interaction in recent_history:
            timestamp = interaction["timestamp"].strftime("%H:%M:%S")
            context_str += f"[{timestamp}] User: {interaction['user']}\n"
            context_str += f"[{timestamp}] Azalise: {interaction['assistant']}\n"
        
        return context_str

class MemoryManager:
    _instance: Optional['MemoryManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            
            # Escolher o tipo de memória baseado na configuração
            if MEMORY_CONFIG["method"] == "redis":
                cls._instance.memory = RedisMemoryManager(MEMORY_CONFIG)
            else:
                cls._instance.memory = SimpleMemory()
                
        return cls._instance
    
    def add_dialog_memory(self, user_text: str, ai_response: str, context: dict = None):
        self.memory.add_dialog_memory(user_text, ai_response, context)
    
    def get_relevant_context(self, current_text: str, limit: int = 5) -> str:
        return self.memory.get_relevant_context(current_text, limit)

    async def get_relevant_context_async(self, prompt):
        # Async version of get_relevant_context
        return await asyncio.to_thread(self.get_relevant_context, prompt)
        
    async def add_dialog_memory_async(self, prompt, response):
        # Async version of add_dialog_memory
        return await asyncio.to_thread(self.add_dialog_memory, prompt, response)

