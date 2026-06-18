"""KnowMind RAG 检索辅助函数。"""

from typing import Any

from backend.indexing.embedding import EmbeddingService, embedding_service
from backend.indexing.milvus_client import MilvusStore, get_milvus_store


LEAF_RETRIEVE_LEVEL = 3


def retrieve_documents(
    query: str,
    top_k: int = 5,
    *,
    embedding: EmbeddingService | None = None,
    milvus_store: MilvusStore | None = None,
) -> dict[str, Any]:
    """将问题转换为稠密向量并召回相似的 L3 叶子分块。"""
    clean_query = query.strip()
    if not clean_query:
        raise ValueError("检索问题不能为空")
    if top_k <= 0:
        raise ValueError("检索 top_k 必须大于 0")

    resolved_embedding = embedding or embedding_service
    resolved_store = milvus_store or get_milvus_store()
    dense_embedding = resolved_embedding.get_embeddings([clean_query])[0]
    documents = resolved_store.dense_retrieve(
        dense_embedding=dense_embedding,
        top_k=top_k,
        filter_expr=f"chunk_level == {LEAF_RETRIEVE_LEVEL}",
    )
    return {
        "docs": documents,
        "meta": {
            "retrieval_mode": "dense",
            "retrieval_pipeline": "dense_only",
            "retrieval_top_k": top_k,
            "leaf_retrieve_level": LEAF_RETRIEVE_LEVEL,
            "recall_count": len(documents),
            "retrieval_empty": not documents,
        },
    }
