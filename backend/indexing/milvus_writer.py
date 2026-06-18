"""KnowMind L3 叶子分块稠密向量入库模块。"""

from typing import Any

from backend.indexing.embedding import EmbeddingService, embedding_service
from backend.indexing.milvus_client import MilvusStore, get_milvus_store


class MilvusWriter:
    """将 L3 叶子分块批量向量化并写入 Milvus。"""

    def __init__(
        self,
        embedding: EmbeddingService | None = None,
        milvus_store: MilvusStore | None = None,
    ) -> None:
        """初始化稠密向量服务和 Milvus Store。"""
        self.embedding = embedding or embedding_service
        self.milvus_store = milvus_store or get_milvus_store()

    def _normalize_leaf_chunk(self, chunk: dict[str, Any]) -> dict[str, Any] | None:
        """筛选并规范化可写入 Milvus 的 L3 叶子分块。"""
        if int(chunk.get("chunk_level") or 0) != 3:
            return None

        text = str(chunk.get("text") or "").strip()
        filename = str(chunk.get("filename") or "").strip()
        chunk_id = str(chunk.get("chunk_id") or "").strip()
        parent_chunk_id = str(chunk.get("parent_chunk_id") or "").strip()
        root_chunk_id = str(chunk.get("root_chunk_id") or "").strip()
        if not text or not filename or not chunk_id or not parent_chunk_id or not root_chunk_id:
            return None

        return {
            "text": text,
            "filename": filename,
            "file_type": str(chunk.get("file_type") or ""),
            "file_path": str(chunk.get("file_path") or ""),
            "page_number": int(chunk.get("page_number") or 0),
            "chunk_idx": int(chunk.get("chunk_idx") or 0),
            "chunk_id": chunk_id,
            "parent_chunk_id": parent_chunk_id,
            "root_chunk_id": root_chunk_id,
            "chunk_level": 3,
        }

    def write_documents(self, documents: list[dict[str, Any]], batch_size: int = 50) -> int:
        """批量生成 dense 向量并写入有效 L3 chunk。"""
        leaf_chunks = [
            normalized
            for document in documents
            if (normalized := self._normalize_leaf_chunk(document)) is not None
        ]
        if not leaf_chunks:
            return 0
        if batch_size <= 0:
            raise ValueError("Milvus 写入批次必须大于 0")

        self.milvus_store.init_collection(self.embedding.dimension)
        written_count = 0
        for start in range(0, len(leaf_chunks), batch_size):
            batch = leaf_chunks[start : start + batch_size]
            vectors = self.embedding.get_embeddings([chunk["text"] for chunk in batch])
            payload = [
                {
                    "dense_embedding": vector,
                    **chunk,
                }
                for chunk, vector in zip(batch, vectors)
            ]
            self.milvus_store.insert(payload)
            written_count += len(payload)
        return written_count

    def replace_documents(
        self,
        filename: str,
        documents: list[dict[str, Any]],
        batch_size: int = 50,
    ) -> int:
        """删除同名旧向量后写入新的 L3 chunk。"""
        self.milvus_store.init_collection(self.embedding.dimension)
        self.milvus_store.delete_by_filename(filename)
        return self.write_documents(documents, batch_size=batch_size)
