"""使用真实 Embedding 和 Milvus 验证 Dense-only 检索闭环。"""

from uuid import uuid4

from backend.indexing.embedding import embedding_service
from backend.indexing.milvus_client import MilvusSettings, MilvusStore
from backend.indexing.milvus_writer import MilvusWriter
from backend.rag.utils import retrieve_documents


def build_test_chunks(filename: str) -> list[dict]:
    """创建语义可区分的临时 L3 测试分块。"""
    texts = [
        "星穹蓝莓协议规定，观测设备必须每三十七天完成一次精密校准。",
        "城市园林养护要求在春季修剪常绿灌木，并及时补充土壤水分。",
        "财务归档流程要求纸质发票按月份排序，并保存对应电子扫描件。",
    ]
    return [
        {
            "text": text,
            "filename": filename,
            "file_type": "txt",
            "file_path": f"data/documents/{filename}",
            "page_number": 1,
            "chunk_idx": index,
            "chunk_id": f"{filename}:chunk:{index}",
            "parent_chunk_id": f"{filename}:parent:{index}",
            "root_chunk_id": f"{filename}:root",
            "chunk_level": 3,
        }
        for index, text in enumerate(texts)
    ]


def drop_test_collection(store: MilvusStore) -> None:
    """删除临时 collection，避免验证数据残留。"""
    with store.session() as client:
        if client.has_collection(store.collection_name):
            client.drop_collection(store.collection_name)


def main() -> None:
    """执行空库、真实写入和问题召回验证。"""
    base_settings = MilvusSettings.from_env()
    collection_name = f"knowmind_f14_verify_{uuid4().hex[:8]}"
    settings = MilvusSettings(
        host=base_settings.host,
        port=base_settings.port,
        collection_name=collection_name,
        uri=base_settings.uri,
        timeout=base_settings.timeout,
    )
    store = MilvusStore(settings)
    writer = MilvusWriter(embedding=embedding_service, milvus_store=store)
    filename = "__f14_dense_retrieval_verify__.txt"

    try:
        empty_result = store.dense_retrieve(
            [0.0] * embedding_service.dimension,
            top_k=1,
            filter_expr="chunk_level == 3",
        )
        if empty_result:
            raise AssertionError("临时空库不应返回检索结果")

        written_count = writer.write_documents(build_test_chunks(filename))
        if written_count != 3:
            raise AssertionError(f"测试向量写入数量错误：{written_count}")

        result = retrieve_documents(
            "星穹蓝莓协议要求观测设备间隔多少天校准一次？",
            top_k=3,
            embedding=embedding_service,
            milvus_store=store,
        )
        documents = result["docs"]
        if not documents:
            raise AssertionError("真实问题未召回任何 chunk")
        if documents[0]["chunk_id"] != f"{filename}:chunk:0":
            raise AssertionError(
                f"目标 chunk 未排在首位，实际为：{documents[0]['chunk_id']}"
            )

        print(
            "真实 Dense-only 检索通过："
            f"写入 {written_count} 个 chunk，召回 {len(documents)} 个，"
            f"首位 chunk={documents[0]['chunk_id']}"
        )
    finally:
        drop_test_collection(store)


if __name__ == "__main__":
    main()
