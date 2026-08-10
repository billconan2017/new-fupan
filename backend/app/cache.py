import json
import redis.asyncio as aioredis
from app.config import get_settings

settings = get_settings()

class RedisCache:
    def __init__(self):
        self._redis = None
    
    async def connect(self):
        self._redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
    
    async def disconnect(self):
        if self._redis:
            await self._redis.close()
    
    async def get(self, key: str):
        if not self._redis:
            return None
        val = await self._redis.get(key)
        return json.loads(val) if val else None
    
    async def set(self, key: str, value, ttl: int = 60):
        if not self._redis:
            return
        await self._redis.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl)
    
    async def delete(self, key: str):
        if self._redis:
            await self._redis.delete(key)
    
    async def exists(self, key: str) -> bool:
        if not self._redis:
            return False
        return bool(await self._redis.exists(key))

cache = RedisCache()
