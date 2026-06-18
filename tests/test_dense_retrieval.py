"""Dense-only 检索单元测试。"""

import unittest
from typing import Any
from unittest.mock import Mock

from backend.indexing.milvus_client import MilvusSettings, MilvusStore
from backend.rag.utils import retrieve_documents


class FakeEmbeddingService:
    """记录输入并返回固定稠密向量的测试服务。"""

    def __init__(self) -> None:
        """初始化测试调用记录。"""
        self.received_texts: list[str] = []

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """返回与输入数量一致的固定向量。"""
        self.received_texts = texts
        return [[0.1, 0.2, 0.3] for _ in texts]


class FakeMilvusStore:
    """记录 dense 检索参数并返回固定 chunk 的测试 Store。"""

    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        """初始化测试结果和调用参数。"""
        self.documents = documents or []
        self.call_args: dict[str, Any] = {}

    def dense_retrieve(
        self,
        dense_embedding: list[float],
        top_k: int = 5,
        filter_expr: str = "",
    ) -> list[dict[str, Any]]:
        """记录检索参数并返回预置文档。"""
        self.call_args = {
            "dense_embedding": dense_embedding,
            "top_k": top_k,
            "filter_expr": filter_expr,
        }
        return self.documents[:top_k]


class DenseRetrievalTestCase(unittest.TestCase):
    """验证 Dense-only 检索的参数传递、结果整形和边界行为。"""

    def test_retrieve_documents_returns_dense_result(self) -> None:
        """问题应被向量化，并只检索 L3 叶子分块。"""
        embedding = FakeEmbeddingService()
        store = FakeMilvusStore(
            documents=[
                {
                    "chunk_id": "chunk-1",
                    "text": "KnowMind 使用 Milvus 保存叶子分块。",
                    "score": 0.92,
                }
            ]
        )

        result = retrieve_documents(
            "  KnowMind 如何保存叶子分块？  ",
            top_k=3,
            embedding=embedding,  # type: ignore[arg-type]
            milvus_store=store,  # type: ignore[arg-type]
        )

        self.assertEqual(embedding.received_texts, ["KnowMind 如何保存叶子分块？"])
        self.assertEqual(store.call_args["dense_embedding"], [0.1, 0.2, 0.3])
        self.assertEqual(store.call_args["top_k"], 3)
        self.assertEqual(store.call_args["filter_expr"], "chunk_level == 3")
        self.assertEqual(result["docs"][0]["chunk_id"], "chunk-1")
        self.assertEqual(result["meta"]["retrieval_mode"], "dense")
        self.assertFalse(result["meta"]["retrieval_empty"])

    def test_retrieve_documents_reports_empty_result(self) -> None:
        """没有召回 chunk 时应返回稳定的空结果元数据。"""
        result = retrieve_documents(
            "不存在的知识",
            embedding=FakeEmbeddingService(),  # type: ignore[arg-type]
            milvus_store=FakeMilvusStore(),  # type: ignore[arg-type]
        )

        self.assertEqual(result["docs"], [])
        self.assertEqual(result["meta"]["recall_count"], 0)
        self.assertTrue(result["meta"]["retrieval_empty"])

    def test_retrieve_documents_rejects_invalid_input(self) -> None:
        """空问题和非正 top_k 应在调用外部服务前失败。"""
        with self.assertRaisesRegex(ValueError, "检索问题不能为空"):
            retrieve_documents("   ")
        with self.assertRaisesRegex(ValueError, "检索 top_k 必须大于 0"):
            retrieve_documents("有效问题", top_k=0)

    def test_milvus_store_formats_dense_hits(self) -> None:
        """Milvus 原始命中应被转换为统一的文档字段。"""
        settings = MilvusSettings(
            host="127.0.0.1",
            port="19530",
            collection_name="test_embeddings",
            uri="http://127.0.0.1:19530",
            timeout=1,
        )
        store = MilvusStore(settings)
        client = Mock()
        client.has_collection.return_value = True
        client.search.return_value = [
            [
                {
                    "id": 7,
                    "distance": 0.88,
                    "entity": {
                        "text": "目标知识片段",
                        "filename": "target.docx",
                        "file_type": "docx",
                        "file_path": "data/documents/target.docx",
                        "page_number": 1,
                        "chunk_idx": 2,
                        "chunk_id": "chunk-7",
                        "parent_chunk_id": "parent-7",
                        "root_chunk_id": "root-7",
                        "chunk_level": 3,
                    },
                }
            ]
        ]
        store._run = Mock(side_effect=lambda operation: operation(client))  # type: ignore[method-assign]

        result = store.dense_retrieve([0.1, 0.2, 0.3], top_k=2, filter_expr="chunk_level == 3")

        self.assertEqual(result[0]["chunk_id"], "chunk-7")
        self.assertEqual(result[0]["score"], 0.88)
        client.search.assert_called_once_with(
            collection_name="test_embeddings",
            data=[[0.1, 0.2, 0.3]],
            anns_field="dense_embedding",
            search_params={"metric_type": "IP", "params": {"ef": 64}},
            limit=2,
            output_fields=[
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
            ],
            filter="chunk_level == 3",
            consistency_level="Strong",
        )


if __name__ == "__main__":
    unittest.main()
