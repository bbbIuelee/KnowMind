"""KnowMind 父级分块 PostgreSQL 存储模块。"""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from backend.db.models import ParentChunk
from backend.infra.cache import cache
from backend.infra.database import SessionLocal


PARENT_CHUNK_LEVELS = {1, 2}


class ParentChunkStore:
    """父级分块存储服务，负责 L1/L2 分块的写入、读取和删除。"""

    def __init__(self, session_factory: sessionmaker[Session] = SessionLocal) -> None:
        """初始化数据库会话工厂。"""
        self.session_factory = session_factory

    def _build_cache_key(self, chunk_id: str) -> str:
        """生成父级分块缓存 key。"""
        return f"parent_chunk:{chunk_id}"

    def _to_dict(self, parent_chunk: ParentChunk) -> dict[str, Any]:
        """将父级分块 ORM 对象转换为可缓存字典。"""
        return {
            "chunk_id": parent_chunk.chunk_id,
            "text": parent_chunk.text,
            "filename": parent_chunk.filename,
            "file_type": parent_chunk.file_type,
            "file_path": parent_chunk.file_path,
            "page_number": parent_chunk.page_number,
            "parent_chunk_id": parent_chunk.parent_chunk_id,
            "root_chunk_id": parent_chunk.root_chunk_id,
            "chunk_level": parent_chunk.chunk_level,
            "chunk_idx": parent_chunk.chunk_idx,
            "updated_at": parent_chunk.updated_at.isoformat(),
        }

    def _normalize_chunk(self, chunk: dict[str, Any]) -> dict[str, Any] | None:
        """筛选并规范化可写入 PostgreSQL 的父级分块。"""
        chunk_level = int(chunk.get("chunk_level") or 0)
        if chunk_level not in PARENT_CHUNK_LEVELS:
            return None

        chunk_id = str(chunk.get("chunk_id") or "").strip()
        text = str(chunk.get("text") or "").strip()
        filename = str(chunk.get("filename") or "").strip()
        if not chunk_id or not text or not filename:
            return None

        return {
            "chunk_id": chunk_id,
            "text": text,
            "filename": filename,
            "file_type": str(chunk.get("file_type") or ""),
            "file_path": str(chunk.get("file_path") or ""),
            "page_number": int(chunk.get("page_number") or 0),
            "parent_chunk_id": str(chunk.get("parent_chunk_id") or ""),
            "root_chunk_id": str(chunk.get("root_chunk_id") or chunk_id),
            "chunk_level": chunk_level,
            "chunk_idx": int(chunk.get("chunk_idx") or 0),
        }

    def _upsert_parent_chunk(self, db_session: Session, payload: dict[str, Any]) -> ParentChunk:
        """在数据库中新增或更新单个父级分块。"""
        parent_chunk = db_session.get(ParentChunk, payload["chunk_id"])
        now = datetime.utcnow()
        if parent_chunk is None:
            parent_chunk = ParentChunk(**payload, updated_at=now)
            db_session.add(parent_chunk)
            return parent_chunk

        for field_name, field_value in payload.items():
            setattr(parent_chunk, field_name, field_value)
        parent_chunk.updated_at = now
        return parent_chunk

    def upsert_documents(self, chunks: list[dict[str, Any]]) -> int:
        """批量写入 L1/L2 父级分块，并同步刷新缓存。"""
        parent_payloads = [
            payload
            for chunk in chunks
            if (payload := self._normalize_chunk(chunk)) is not None
        ]
        if not parent_payloads:
            return 0

        with self.session_factory() as db_session:
            parent_chunks = [
                self._upsert_parent_chunk(db_session, payload)
                for payload in parent_payloads
            ]
            db_session.commit()
            for parent_chunk in parent_chunks:
                db_session.refresh(parent_chunk)
                cache.set_json(
                    self._build_cache_key(parent_chunk.chunk_id),
                    self._to_dict(parent_chunk),
                )
        return len(parent_payloads)

    def get_documents_by_ids(self, chunk_ids: list[str]) -> list[dict[str, Any]]:
        """按 chunk_id 批量读取父级分块，优先使用 Redis 缓存。"""
        ordered_ids = [chunk_id.strip() for chunk_id in chunk_ids if chunk_id and chunk_id.strip()]
        if not ordered_ids:
            return []

        found_chunks: dict[str, dict[str, Any]] = {}
        missed_ids: list[str] = []
        for chunk_id in ordered_ids:
            cached_chunk = cache.get_json(self._build_cache_key(chunk_id))
            if isinstance(cached_chunk, dict):
                found_chunks[chunk_id] = cached_chunk
            else:
                missed_ids.append(chunk_id)

        if missed_ids:
            with self.session_factory() as db_session:
                parent_chunks = (
                    db_session.query(ParentChunk)
                    .filter(ParentChunk.chunk_id.in_(missed_ids))
                    .all()
                )
                for parent_chunk in parent_chunks:
                    payload = self._to_dict(parent_chunk)
                    found_chunks[parent_chunk.chunk_id] = payload
                    cache.set_json(self._build_cache_key(parent_chunk.chunk_id), payload)

        return [
            found_chunks[chunk_id]
            for chunk_id in ordered_ids
            if chunk_id in found_chunks
        ]

    def delete_by_filename(self, filename: str) -> int:
        """按文件名删除父级分块，并删除对应 Redis 缓存。"""
        clean_filename = filename.strip()
        if not clean_filename:
            return 0

        with self.session_factory() as db_session:
            parent_chunks = (
                db_session.query(ParentChunk)
                .filter(ParentChunk.filename == clean_filename)
                .all()
            )
            deleted_ids = [parent_chunk.chunk_id for parent_chunk in parent_chunks]
            for parent_chunk in parent_chunks:
                db_session.delete(parent_chunk)
            db_session.commit()

        for chunk_id in deleted_ids:
            cache.delete(self._build_cache_key(chunk_id))
        return len(deleted_ids)
