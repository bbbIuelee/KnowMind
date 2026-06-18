"""KnowMind Milvus collection 和基础数据访问模块。"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator, TypeVar

from pymilvus import DataType, MilvusClient

from backend.env import load_env


load_env()

T = TypeVar("T")


@dataclass(frozen=True)
class MilvusSettings:
    """Milvus 连接和 collection 配置。"""

    host: str
    port: str
    collection_name: str
    uri: str
    timeout: float

    @classmethod
    def from_env(cls) -> MilvusSettings:
        """从环境变量读取 Milvus 配置。"""
        host = os.getenv("MILVUS_HOST", "127.0.0.1")
        port = os.getenv("MILVUS_PORT", "19530")
        collection_name = os.getenv("MILVUS_COLLECTION", "knowmind_embeddings")
        timeout = float(os.getenv("MILVUS_TIMEOUT", "30"))
        return cls(
            host=host,
            port=port,
            collection_name=collection_name,
            uri=f"http://{host}:{port}",
            timeout=timeout,
        )


@contextmanager
def milvus_client_session(settings: MilvusSettings | None = None) -> Iterator[MilvusClient]:
    """创建一次短生命周期 Milvus 连接，并在使用后关闭。"""
    resolved_settings = settings or MilvusSettings.from_env()
    client = MilvusClient(uri=resolved_settings.uri, timeout=resolved_settings.timeout)
    try:
        yield client
    finally:
        client.close()


class MilvusStore:
    """Milvus 基础存储服务，不长期持有网络连接。"""

    def __init__(self, settings: MilvusSettings | None = None) -> None:
        """初始化 Milvus 配置。"""
        self._settings = settings or MilvusSettings.from_env()

    @property
    def collection_name(self) -> str:
        """返回当前使用的 collection 名称。"""
        return self._settings.collection_name

    def _run(self, operation: Callable[[MilvusClient], T]) -> T:
        """在短生命周期连接中执行一次 Milvus 操作。"""
        with milvus_client_session(self._settings) as client:
            return operation(client)

    @contextmanager
    def session(self) -> Iterator[MilvusClient]:
        """为同一业务批次提供可复用的短生命周期连接。"""
        with milvus_client_session(self._settings) as client:
            yield client

    @staticmethod
    def _read_dense_dimension(description: dict) -> int | None:
        """从 collection 描述中读取 dense_embedding 维度。"""
        for field in description.get("fields", []):
            if field.get("name") != "dense_embedding":
                continue
            params = field.get("params") or {}
            dimension = params.get("dim")
            return int(dimension) if dimension is not None else None
        return None

    @staticmethod
    def ensure_collection(client: MilvusClient, collection_name: str, dense_dim: int) -> None:
        """确保 dense-only collection 和 HNSW 索引存在且维度正确。"""
        if client.has_collection(collection_name):
            description = client.describe_collection(collection_name)
            existing_dimension = MilvusStore._read_dense_dimension(description)
            if existing_dimension != dense_dim:
                raise RuntimeError(
                    f"Milvus collection 向量维度不匹配：期望 {dense_dim}，实际 {existing_dimension}"
                )
            client.load_collection(collection_name)
            return

        schema = client.create_schema(auto_id=True, enable_dynamic_field=False)
        schema.add_field("id", DataType.INT64, is_primary=True, auto_id=True)
        schema.add_field("dense_embedding", DataType.FLOAT_VECTOR, dim=dense_dim)
        schema.add_field("text", DataType.VARCHAR, max_length=8192)
        schema.add_field("filename", DataType.VARCHAR, max_length=255)
        schema.add_field("file_type", DataType.VARCHAR, max_length=50)
        schema.add_field("file_path", DataType.VARCHAR, max_length=1024)
        schema.add_field("page_number", DataType.INT64)
        schema.add_field("chunk_idx", DataType.INT64)
        schema.add_field("chunk_id", DataType.VARCHAR, max_length=512)
        schema.add_field("parent_chunk_id", DataType.VARCHAR, max_length=512)
        schema.add_field("root_chunk_id", DataType.VARCHAR, max_length=512)
        schema.add_field("chunk_level", DataType.INT64)

        index_params = client.prepare_index_params()
        index_params.add_index(
            field_name="dense_embedding",
            index_type="HNSW",
            metric_type="IP",
            params={"M": 16, "efConstruction": 256},
        )
        client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )
        client.load_collection(collection_name)

    @staticmethod
    def _escape_filter_value(value: str) -> str:
        """转义 Milvus 字符串过滤条件中的特殊字符。"""
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def init_collection(self, dense_dim: int | None = None) -> None:
        """初始化当前配置对应的 dense-only collection。"""
        resolved_dimension = dense_dim or int(os.getenv("DENSE_EMBEDDING_DIM", "1024"))

        def initialize(client: MilvusClient) -> None:
            """在当前连接中创建或校验 collection。"""
            self.ensure_collection(client, self.collection_name, resolved_dimension)

        self._run(initialize)

    def insert(self, data: list[dict]) -> dict:
        """向当前 collection 批量插入 L3 chunk。"""
        if not data:
            return {"insert_count": 0}
        return self._run(lambda client: client.insert(self.collection_name, data))

    def delete_by_filename(self, filename: str) -> int:
        """按文件名删除旧 L3 chunk，并返回删除数量。"""
        clean_filename = filename.strip()
        if not clean_filename:
            return 0
        escaped_filename = self._escape_filter_value(clean_filename)

        def delete_rows(client: MilvusClient) -> int:
            """在当前连接中删除指定文件的向量记录。"""
            if not client.has_collection(self.collection_name):
                return 0
            result = client.delete(
                collection_name=self.collection_name,
                filter=f'filename == "{escaped_filename}"',
            )
            return int(result.get("delete_count", 0)) if isinstance(result, dict) else 0

        return self._run(delete_rows)

    def query_by_filename(
        self,
        filename: str,
        output_fields: list[str] | None = None,
        limit: int = 10000,
    ) -> list[dict]:
        """按文件名查询 L3 元数据，用于入库验证和同名清理。"""
        clean_filename = filename.strip()
        if not clean_filename:
            return []
        escaped_filename = self._escape_filter_value(clean_filename)
        fields = output_fields or [
            "text",
            "filename",
            "file_type",
            "file_path",
            "page_number",
            "chunk_idx",
            "chunk_id",
            "parent_chunk_id",
            "root_chunk_id",
            "chunk_level",
        ]

        def query_rows(client: MilvusClient) -> list[dict]:
            """在当前连接中查询指定文件的向量记录。"""
            if not client.has_collection(self.collection_name):
                return []
            return client.query(
                collection_name=self.collection_name,
                filter=f'filename == "{escaped_filename}"',
                output_fields=fields,
                limit=limit,
                consistency_level="Strong",
            )

        return self._run(query_rows)

    def describe_collection(self) -> dict:
        """返回当前 collection 的结构描述。"""
        return self._run(lambda client: client.describe_collection(self.collection_name))


_milvus_store: MilvusStore | None = None


def get_milvus_store() -> MilvusStore:
    """返回进程内共享的无状态 Milvus Store。"""
    global _milvus_store
    if _milvus_store is None:
        _milvus_store = MilvusStore()
    return _milvus_store
