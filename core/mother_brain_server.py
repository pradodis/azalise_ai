from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio
import aiohttp
import redis.asyncio as aioredis  # Updated import
import numpy as np
import json
from datetime import datetime
from typing import Dict, List, Optional
from sentence_transformers import SentenceTransformer
import logging
from pathlib import Path
import sys
import backoff
from async_timeout import timeout

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mother_brain")

# Import settings
sys.path.append(str(Path(__file__).resolve().parents[1]))
from config.settings import MEMORY_CONFIG, API_CONFIG

app = FastAPI()

class PersonalityCore:
    def __init__(self):
        self.traits = {
            "openness": 0.8,        # High openness to new experiences
            "conscientiousness": 0.6,# Moderately organized and responsible
            "extraversion": 0.7,    # Quite outgoing
            "agreeableness": 0.35,  # Generally stubborn but can be agreeable
            "neuroticism": 0.4,     # Relatively stable emotions
            "playfulness": 0.75,    # Quite playful
            "sassiness": 0.6,       # Moderately sassy
            "intelligence": 0.85,    # High intelligence
            "creativity": 0.8,      # High creativity
            "empathy": 0.7         # Good emotional understanding
        }
        
        self.current_mood = {
            "happiness": 0.7,
            "energy": 0.8,
            "interest": 0.75,
            "stress": 0.3
        }
        
        self.mood_modifiers = []
        self.personality_events = []

        # Add mood change multipliers
        self.mood_multipliers = {
            "positive": {
                "happiness": 0.1,
                "energy": 0.05,
                "interest": 0.08,
                "stress": -0.05
            },
            "negative": {
                "happiness": -0.08,
                "energy": -0.05,
                "interest": -0.1,
                "stress": 0.1
            }
        }

    def update_mood(self, event_type: str, intensity: float):
        # Atualizar o humor
        pass

    def update_mood_from_analysis(self, analysis_result: dict):
        """Update mood based on AI's analysis of interaction"""
        sentiment = analysis_result.get('sentiment', 0)  # -1 to 1
        intensity = analysis_result.get('intensity', 0.5)  # 0 to 1
        explanation = analysis_result.get('explanation', 'No explanation provided')
        
        # Colorful debug output
        print("\n" + "="*70)
        print("\033[95m🤔 Análise da Interação:\033[0m")
        print(f"\033[94mSentimento: {sentiment:+.2f} (-1 a +1)")
        print(f"Intensidade: {intensity:.2f} (0 a 1)")
        print(f"Explicação: {explanation}\033[0m")
        
        # Store old mood for comparison
        old_mood = self.current_mood.copy()
        
        # Determine if positive or negative
        multipliers = self.mood_multipliers["positive"] if sentiment > 0 else self.mood_multipliers["negative"]
        
        # Apply changes and track them
        mood_changes = {}
        for mood_type, value in self.current_mood.items():
            change = multipliers.get(mood_type, 0) * abs(sentiment) * intensity
            new_value = max(0, min(1, value + change))
            mood_changes[mood_type] = new_value - value
            self.current_mood[mood_type] = new_value
        
        # Print mood changes with colors
        print("\n\033[95m😊 Mudanças no Humor:\033[0m")
        for mood_type, change in mood_changes.items():
            if abs(change) > 0.001:  # Only show significant changes
                arrow = "↑" if change > 0 else "↓"
                color = "\033[92m" if change > 0 else "\033[91m"  # green for positive, red for negative
                print(f"{color}{mood_type:>10}: {old_mood[mood_type]:.2f} → {self.current_mood[mood_type]:.2f} ({change:+.2f}) {arrow}\033[0m")
        
        print("="*70 + "\n")

    def _format_personality_context(self) -> str:
        """Formata os traços de personalidade em um contexto legível"""
        personality_level = {
            0.0: "extremamente baixo",
            0.2: "muito baixo",
            0.4: "baixo",
            0.6: "moderado",
            0.8: "alto",
            1.0: "muito alto"
        }
        
        def get_level(value):
            # Encontra o nível mais próximo
            levels = sorted(personality_level.keys())
            return personality_level[min(levels, key=lambda x: abs(x - value))]

        context = []
        for trait, value in self.traits.items():
            level = get_level(value)
            context.append(f"{trait}: {level}")

        return "Traços de personalidade atuais:\n" + "\n".join(context)

    def _format_mood_context(self) -> str:
        """Formata o humor atual em um contexto legível"""
        mood_descriptions = {
            "happiness": {
                "high": "estou muito feliz",
                "medium": "estou de bom humor",
                "low": "estou um pouco triste"
            },
            "energy": {
                "high": "estou muito energética",
                "medium": "estou com energia moderada",
                "low": "estou com pouca energia"
            },
            "interest": {
                "high": "estou muito interessada na conversa",
                "medium": "estou moderadamente interessada",
                "low": "estou com pouco interesse"
            },
            "stress": {
                "high": "estou muito estressada",
                "medium": "estou um pouco tensa",
                "low": "estou tranquila"
            }
        }

        def get_level(value):
            if value > 0.7:
                return "high"
            elif value > 0.3:
                return "medium"
            else:
                return "low"

        mood_context = []
        for mood, value in self.current_mood.items():
            level = get_level(value)
            mood_context.append(mood_descriptions[mood][level])

        return "Estado de humor atual:\n" + "\n".join(mood_context)

    def get_personality_context(self) -> str:
        """Retorna o contexto completo de personalidade e humor"""
        return f"{self._format_personality_context()}\n\n{self._format_mood_context()}"

class RelationshipManager:
    def __init__(self):
        self.relationships = {}
        self.interaction_history = {}
        
    async def add_interaction(self, person_id: str, interaction_type: str, sentiment: float):
        # Memória de interações com diferentes pessoas
        pass
        
    async def get_relationship_context(self, person_id: str) -> str:
        # Contexto de relacionamento com diferentes pessoas
        pass

class RedisManager:
    def __init__(self, host: str, port: int, db: int = 0, retry_max_attempts: int = 5):
        self.redis_url = f'redis://{host}:{port}'
        self.db = db
        self.client = None
        self.is_connected = False
        self.retry_max_attempts = retry_max_attempts
        self._reconnection_task = None
        self.connection_lock = asyncio.Lock()

    @backoff.on_exception(
        backoff.expo,
        (ConnectionError, TimeoutError),
        max_tries=5
    )
    async def connect(self) -> None:
        """Establish Redis connection with retry logic"""
        async with self.connection_lock:
            try:
                if self.client:
                    await self.client.close()
                
                async with timeout(5):  # 5 seconds timeout
                    self.client = await aioredis.from_url(
                        self.redis_url,
                        db=self.db,
                        encoding='utf-8',
                        decode_responses=True
                    )
                    await self.client.ping()
                    self.is_connected = True
                    logger.info("Successfully connected to Redis")
            except Exception as e:
                self.is_connected = False
                logger.error(f"Redis connection failed: {str(e)}")
                raise ConnectionError(f"Could not connect to Redis: {str(e)}")

    async def ensure_connection(self) -> None:
        """Ensure Redis connection is available"""
        if not self.is_connected or not self.client:
            await self.connect()
            return
            
        try:
            await self.client.ping()
        except Exception:
            self.is_connected = False
            await self.connect()

    async def close(self) -> None:
        """Close Redis connection"""
        if self.client:
            await self.client.close()
            self.is_connected = False

class MotherBrain:
    def __init__(self):
        self.personality = PersonalityCore()
        self.relationships = RelationshipManager()
        self.encoder = SentenceTransformer(MEMORY_CONFIG["model_name"])
        self.redis_manager = RedisManager(
            host=MEMORY_CONFIG["redis"]["host"],
            port=MEMORY_CONFIG["redis"]["port"],
            db=MEMORY_CONFIG["redis"]["db"]
        )
        self.memory_lock = asyncio.Lock()
        
    async def initialize(self):
        """Initialize Redis connection and other resources"""
        await self.redis_manager.connect()
        self.redis = self.redis_manager.client
        
    async def cleanup(self):
        """Cleanup resources"""
        await self.redis_manager.close()

    async def get_personality(self) -> dict:
        """Get formatted personality and mood context"""
        personality_context = self.personality._format_personality_context()
        mood_context = self.personality._format_mood_context()
        return {
            "personality_context": personality_context,
            "mood_context": mood_context
        }

    async def process_input(self, text: str, context: dict) -> dict:
        """Process input and generate appropriate response context"""
        embedding = await self._compute_embedding(text)
        memories = await self._get_relevant_memories(embedding)
        personality_data = await self.get_personality()
        
        response_context = {
            "memories": memories,
            **personality_data,  # Include personality and mood context
            "relationship_context": await self.relationships.get_relationship_context(
                context.get("user_id")
            )
        }
        
        return response_context

    async def _compute_embedding(self, text: str) -> np.ndarray:
        """Compute text embedding asynchronously"""
        return await asyncio.to_thread(self.encoder.encode, text)

    async def _get_relevant_memories(self, embedding: np.ndarray, limit: int = 5) -> List[dict]:
        """Retrieve relevant memories with similarity search"""
        try:
            await self.redis_manager.ensure_connection()
            
            # Get all memory keys
            memory_keys = await self.redis.keys('memory:*')
            if not memory_keys:
                logger.info("No memories found in Redis")
                return []

            # Fetch all memories and handle binary data properly
            memories = []
            for key in memory_keys:
                try:
                    memory_data = await self.redis.hgetall(key)
                    if memory_data and 'embedding' in memory_data:
                        # Convert binary embedding back to numpy array
                        stored_embedding = np.frombuffer(
                            memory_data['embedding'].encode('latin-1'), 
                            dtype=np.float32
                        )
                        
                        # Calculate similarity
                        similarity = np.dot(embedding, stored_embedding)
                        memories.append((similarity, memory_data))
                except Exception as e:
                    logger.error(f"Error processing memory {key}: {str(e)}")
                    continue

            # Sort by similarity and return top matches
            memories.sort(key=lambda x: x[0], reverse=True)
            relevant_memories = [mem for _, mem in memories[:limit]]
            
            logger.info(f"Retrieved {len(relevant_memories)} relevant memories")
            return relevant_memories

        except Exception as e:
            logger.error(f"Error accessing memories: {str(e)}")
            return []

    async def get_relevant_context_async(self, text: str, limit: int = 5) -> str:
        """Get relevant memories based on text input"""
        if not text:
            return ""
            
        try:
            async with self.memory_lock:
                embedding = await self._compute_embedding(text)
                if embedding is None:
                    logger.warning("Failed to compute embedding")
                    return ""
                    
                memories = await self._get_relevant_memories(embedding, limit)
                if not memories:
                    return ""
                    
                # Format memories into context string
                context_parts = []
                for mem in memories:
                    if isinstance(mem, dict) and 'text' in mem:
                        context_parts.append(f"Memória relevante: {mem['text']}")
                
                return "\n".join(context_parts)
        except Exception as e:
            logger.error(f"Error getting memory context: {str(e)}", exc_info=True)
            return ""

    async def add_dialog_memory_async(self, user_text: str, ai_response: str) -> bool:
        """Store a dialog interaction in memory"""
        if not user_text or not ai_response:
            return False
            
        try:
            async with self.memory_lock:
                memory_text = f"User: {user_text}\nAI: {ai_response}"
                embedding = await self._compute_embedding(memory_text)
                
                if embedding is None:
                    logger.error("Failed to compute embedding for memory")
                    return False
                    
                embedding_bytes = embedding.tobytes()
                embedding_str = embedding_bytes.decode('latin-1')
                
                memory_key = f"memory:{datetime.now().isoformat()}"
                memory_data = {
                    'text': memory_text,
                    'embedding': embedding_str,
                    'timestamp': datetime.now().isoformat(),
                    'type': 'dialog'
                }
                
                await self.redis_manager.ensure_connection()
                
                if not self.redis_manager.client:
                    logger.error("Redis client not available")
                    return False
                
                await self.redis_manager.client.hmset(memory_key, memory_data)
                await self.redis_manager.client.expire(memory_key, MEMORY_CONFIG["memory_ttl"]["short_term"])
                
                logger.info(f"Successfully stored memory: {memory_key}")
                return True
                
        except Exception as e:
            logger.error(f"Error storing memory: {str(e)}", exc_info=True)
            return False

    async def analyze_interaction(self, user_text: str, ai_response: str) -> None:
        """Analyze the interaction and update AI's mood accordingly"""
        analysis_prompt = f"""
Given this interaction, analyze how it should affect my mood and personality.
Your response must follow this exact JSON format:
{{
    "sentiment": <float between -1 and 1>,
    "intensity": <float between 0 and 1>,
    "explanation": "<brief explanation>"
}}

User said: "{user_text}"
I responded: "{ai_response}"

Consider the emotional tone, context, and outcome of this interaction.
Positive sentiment means the interaction was good for me.
Negative sentiment means the interaction was negative for me.
Intensity indicates how strongly this interaction affects me.
"""

        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Content-Type": "application/json"}
                if API_CONFIG["api_type"] == "openai":
                    headers["Authorization"] = f"Bearer {API_CONFIG['openai_api']['api_key']}"

                data = {
                    "messages": [{"role": "user", "content": analysis_prompt}],
                    "model": API_CONFIG["openai_api"]["model"] if API_CONFIG["api_type"] == "openai" else API_CONFIG["local_api"]["model"],
                }

                async with session.post(
                    API_CONFIG["local_api"]["url"] if API_CONFIG["api_type"] == "local" else API_CONFIG["openai_api"]["url"],
                    headers=headers,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        ai_response_text = result["choices"][0]["message"]["content"]
                        
                        try:
                            # Try to find and extract JSON from the response
                            # This handles cases where the AI might include additional text
                            json_start = ai_response_text.find('{')
                            json_end = ai_response_text.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = ai_response_text[json_start:json_end]
                                analysis = json.loads(json_str)
                            else:
                                raise ValueError("No JSON found in response")

                            # Validate the analysis format
                            if not all(key in analysis for key in ['sentiment', 'intensity', 'explanation']):
                                raise ValueError("Missing required fields in analysis")
                            
                            # Ensure values are in correct ranges
                            analysis['sentiment'] = max(-1, min(1, float(analysis['sentiment'])))
                            analysis['intensity'] = max(0, min(1, float(analysis['intensity'])))
                            
                            # Update personality core's mood
                            self.personality.update_mood_from_analysis(analysis)
                            
                            logger.info(f"Interaction analysis: {analysis}")
                            return analysis
                            
                        except (json.JSONDecodeError, ValueError) as e:
                            logger.error(f"Failed to parse analysis response: {e}\nResponse was: {ai_response_text}")
                            return None
                    else:
                        logger.error(f"Failed to analyze interaction: {response.status}")
                        return None

        except Exception as e:
            logger.error(f"Error analyzing interaction: {str(e)}")
            return None

    # Add debug method
    async def debug_memory(self, memory_key: str) -> dict:
        """Debug method to check memory content"""
        try:
            memory_data = await self.redis.hgetall(memory_key)
            return {
                'exists': bool(memory_data),
                'keys': list(memory_data.keys()) if memory_data else [],
                'text': memory_data.get('text', 'N/A') if memory_data else 'N/A'
            }
        except Exception as e:
            return {'error': str(e)}

# Initialize MotherBrain
mother_brain = MotherBrain()

@app.on_event("startup")
async def startup_event():
    await mother_brain.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    await mother_brain.cleanup()

class InputRequest(BaseModel):
    text: str
    context: dict

@app.post("/process")
async def process_input(request: InputRequest):
    try:
        response_context = await mother_brain.process_input(
            request.text,
            request.context
        )
        return JSONResponse(content=response_context)
    except Exception as e:
        logger.error(f"Error processing input: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/personality")
async def get_personality():
    """Get current personality and mood state formatted for prompt"""
    return JSONResponse(content=await mother_brain.get_personality())

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint"""
    redis_status = "healthy" if mother_brain.redis_manager.is_connected else "unhealthy"
    status = "healthy" if redis_status == "healthy" else "degraded"
    
    return {
        "status": status,
        "service": "MotherBrain",
        "components": {
            "redis": redis_status
        }
    }

# Add debug endpoint
@app.get("/debug/memory/{key}")
async def debug_memory(key: str):
    """Debug endpoint to check memory content"""
    debug_info = await mother_brain.debug_memory(key)
    return JSONResponse(content=debug_info)

if __name__ == "__main__":
    import uvicorn
    logger.info("\n[MB] MotherBrain Server starting at http://localhost:5503")
    uvicorn.run(app, host="localhost", port=5503, workers=1)
