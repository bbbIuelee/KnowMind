"""KnowMind Redis 缓存基础设施模块。"""

import json
import os
from typing import Any

import redis

from backend.env import load_env


load_env()


class RedisCache:
    """Redis JSON 缓存客户端，连接失败时自动降级为空操作。"""

    def __init__(self) -> None:
        """按环境变量初始化 Redis 连接配置。"""
        self.redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.key_prefix = os.getenv("REDIS_KEY_PREFIX", "knowmind")
        self.default_ttl = int(os.getenv("REDIS_CACHE_TTL_SECONDS", "3600"))
        self._client: redis.Redis | None = None

    def _get_client(self) -> redis.Redis:
        """懒加载 Redis 客户端。"""
        if self._client is None:
            self._client = redis.Redis.from_url(self.redis_url, decode_responses=True)
        return self._client

    def _build_key(self, key: str) -> str:
        """拼接统一的 Redis key 前缀。"""
        clean_prefix = self.key_prefix.strip(":")
        clean_key = key.strip(":")
        return f"{clean_prefix}:{clean_key}" if clean_prefix else clean_key

    def _reset_client(self) -> None:
        """在 Redis 异常后清空客户端，便于后续重连。"""
        self._client = None

    def get_json(self, key: str) -> Any | None:
        """读取 JSON 缓存，读取失败或不存在时返回 None。"""
        try:
            raw_value = self._get_client().get(self._build_key(key))
            if raw_value is None:
                return None
            return json.loads(raw_value)
        except Exception:
            self._reset_client()
            return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> None:
        """写入 JSON 缓存，写入失败时不影响主流程。"""
        try:
            payload = json.dumps(value, ensure_ascii=False, default=str)
            self._get_client().setex(self._build_key(key), ttl or self.default_ttl, payload)
        except Exception:
            self._reset_client()

    def delete(self, key: str) -> None:
        """删除指定缓存 key，删除失败时不影响主流程。"""
        try:
            self._get_client().delete(self._build_key(key))
        except Exception:
            self._reset_client()


cache = RedisCache()
