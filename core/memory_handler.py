from datetime import datetime
import json
from typing import Dict, List, Optional
from dataclasses import dataclass
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
import redis
import pickle

@dataclass
class Memory:
    content: str
    timestamp: datetime
    importance: float
    context: Dict
    memory_type: str
    embedding: Optional[np.ndarray] = None

class RedisMemoryManager:
    def __init__(self, config: dict):
        redis_config = config["redis"].copy()
        redis_config["decode_responses"] = False  # Change this to False to handle binary data
        self.redis = redis.Redis(**redis_config)
        self.st_memory_limit = config["st_memory_limit"]
        self.importance_threshold = config["importance_threshold"]
        self.ttl = config["memory_ttl"]
        self.encoder = SentenceTransformer(config["model_name"])

    def _compute_embedding(self, text: str) -> np.ndarray:
        with torch.no_grad():
            return self.encoder.encode(text)

    def _calculate_importance(self, content: str, context: Dict) -> float:
        importance = 0.5
        emotional_keywords = ["happy", "sad", "angry", "excited", "worried"]
        importance += sum(0.1 for word in emotional_keywords if word in content.lower())
        
        if "user_emotion" in context:
            importance += 0.2
        if "critical_info" in context:
            importance += 0.3
            
        return min(1.0, importance)

    def add_memory(self, content: str, context: Dict) -> None:
        try:
            importance = self._calculate_importance(content, context)
            embedding = self._compute_embedding(content)
            
            memory = Memory(
                content=content,
                timestamp=datetime.now(),
                importance=importance,
                context=context,
                memory_type='short_term',
                embedding=embedding
            )

            # Store in Redis with proper encoding
            memory_key = f"memory:{datetime.now().timestamp()}".encode('utf-8')
            memory_data = pickle.dumps(memory)
            
            if importance >= self.importance_threshold:
                self.redis.set(b"lt:" + memory_key, memory_data)
                self.redis.expire(b"lt:" + memory_key, self.ttl["long_term"])
            else:
                self.redis.set(b"st:" + memory_key, memory_data)
                self.redis.expire(b"st:" + memory_key, self.ttl["short_term"])

            self._cleanup_short_term()
        except Exception as e:
            print(f"Error adding memory: {str(e)}")

    def _cleanup_short_term(self):
        try:
            st_keys = self.redis.keys(b"st:memory:*")
            if len(st_keys) > self.st_memory_limit:
                memories = []
                for key in st_keys:
                    memory_data = self.redis.get(key)
                    if memory_data:
                        memory = pickle.loads(memory_data)
                        memories.append((key, memory))
                
                memories.sort(key=lambda x: x[1].importance, reverse=True)
                
                for key, _ in memories[self.st_memory_limit:]:
                    self.redis.delete(key)
        except Exception as e:
            print(f"Error in cleanup: {str(e)}")

    def retrieve_relevant_memories(self, query: str, limit: int = 5) -> List[Memory]:
        try:
            query_embedding = self._compute_embedding(query)
            all_memories = []
            
            # Get all memories from Redis using binary patterns
            for key in self.redis.keys(b"*:memory:*"):
                memory_data = self.redis.get(key)
                if memory_data:
                    try:
                        memory = pickle.loads(memory_data)
                        if memory.embedding is not None:
                            similarity = np.dot(query_embedding, memory.embedding)
                            all_memories.append((similarity, memory))
                    except Exception as e:
                        print(f"Error loading memory {key}: {str(e)}")
            
            all_memories.sort(key=lambda x: x[0], reverse=True)
            return [memory for _, memory in all_memories[:limit]]
        except Exception as e:
            print(f"Error retrieving memories: {str(e)}")
            return []
