"""KnowMind 稠密向量生成模块。"""

import os
from typing import Any, Protocol

import requests

from backend.env import load_env


load_env()

DEFAULT_EMBEDDING_ENDPOINT = (
    "https://dashscope.aliyuncs.com/api/v1/services/embeddings/"
    "multimodal-embedding/multimodal-embedding"
)


class DenseEmbedder(Protocol):
    """稠密向量模型协议，便于替换远程模型和注入测试实现。"""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """为一批文本生成稠密向量。"""
        ...


class DashScopeMultimodalEmbeddings:
    """DashScope 多模态向量模型的文本输入适配器。"""

    def __init__(
        self,
        model_name: str,
        api_key: str,
        endpoint: str,
        dimension: int,
        timeout: float,
        batch_size: int,
    ) -> None:
        """初始化 DashScope 向量模型配置。"""
        self.model_name = model_name
        self.api_key = api_key
        self.endpoint = endpoint
        self.dimension = dimension
        self.timeout = timeout
        self.batch_size = max(batch_size, 1)

    def _build_contents(self, texts: list[str]) -> list[dict[str, str]]:
        """将文本列表转换为 DashScope contents 参数。"""
        return [{"text": text or ""} for text in texts]

    def _extract_embeddings(self, body: dict[str, Any], expected_count: int) -> list[list[float]]:
        """从 DashScope 响应中按输入顺序提取向量。"""
        embeddings = body.get("output", {}).get("embeddings")
        if not isinstance(embeddings, list):
            raise RuntimeError("向量接口响应缺少 embeddings 字段")

        ordered_items = sorted(
            embeddings,
            key=lambda item: item.get("index", 0) if isinstance(item, dict) else 0,
        )
        vectors: list[list[float]] = []
        for item in ordered_items:
            raw_vector = item.get("embedding") if isinstance(item, dict) else item
            if not isinstance(raw_vector, list):
                raise RuntimeError("向量接口响应包含无效向量")
            vectors.append([float(value) for value in raw_vector])

        if len(vectors) != expected_count:
            raise RuntimeError(
                f"向量数量不匹配：期望 {expected_count}，实际 {len(vectors)}"
            )
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        """调用一次 DashScope 接口生成一批稠密向量。"""
        try:
            response = requests.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model_name,
                    "input": {"contents": self._build_contents(texts)},
                    "parameters": {"dimension": self.dimension},
                },
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise RuntimeError("向量接口网络请求失败") from exc
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeError(f"向量接口返回非 JSON 响应：HTTP {response.status_code}") from exc

        if response.status_code >= 400:
            message = body.get("message") or body.get("error", {}).get("message") or "未知错误"
            raise RuntimeError(f"向量接口调用失败：HTTP {response.status_code}，{message}")
        return self._extract_embeddings(body, len(texts))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """按配置批次为文本生成稠密向量。"""
        vectors: list[list[float]] = []
        for start in range(0, len(texts), self.batch_size):
            vectors.extend(self._embed_batch(texts[start : start + self.batch_size]))
        return vectors


def create_dense_embedder() -> DenseEmbedder:
    """根据环境变量创建当前阶段支持的稠密向量模型。"""
    provider = os.getenv("EMBEDDING_PROVIDER", "dashscope_multimodal").strip().lower()
    supported_providers = {"dashscope", "dashscope_multimodal", "aliyun", "aliyun_dashscope"}
    if provider not in supported_providers:
        raise ValueError(f"当前阶段不支持稠密向量提供方：{provider}")

    api_key = (
        os.getenv("EMBEDDING_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("ARK_API_KEY")
    )
    if not api_key:
        raise ValueError("未配置 EMBEDDING_API_KEY、DASHSCOPE_API_KEY 或 ARK_API_KEY")

    return DashScopeMultimodalEmbeddings(
        model_name=os.getenv("EMBEDDING_MODEL", "tongyi-embedding-vision-plus-2026-03-06"),
        api_key=api_key,
        endpoint=os.getenv("EMBEDDING_API_URL", DEFAULT_EMBEDDING_ENDPOINT),
        dimension=int(os.getenv("DENSE_EMBEDDING_DIM", "1024")),
        timeout=float(os.getenv("EMBEDDING_TIMEOUT", "60")),
        batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "10")),
    )


class EmbeddingService:
    """稠密向量服务，负责延迟创建模型并校验输出维度。"""

    def __init__(
        self,
        embedder: DenseEmbedder | None = None,
        dimension: int | None = None,
    ) -> None:
        """初始化可选的向量模型和目标维度。"""
        self._embedder = embedder
        self.dimension = dimension or int(os.getenv("DENSE_EMBEDDING_DIM", "1024"))

    def _get_embedder(self) -> DenseEmbedder:
        """延迟创建并返回稠密向量模型。"""
        if self._embedder is None:
            self._embedder = create_dense_embedder()
        return self._embedder

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """生成稠密向量并校验数量和维度。"""
        if not texts:
            return []

        vectors = self._get_embedder().embed_documents(texts)
        if len(vectors) != len(texts):
            raise RuntimeError(f"向量数量不匹配：期望 {len(texts)}，实际 {len(vectors)}")
        for index, vector in enumerate(vectors):
            if len(vector) != self.dimension:
                raise RuntimeError(
                    f"第 {index} 个向量维度不匹配：期望 {self.dimension}，实际 {len(vector)}"
                )
        return vectors


embedding_service = EmbeddingService()
