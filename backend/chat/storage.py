"""KnowMind 聊天会话持久化存储服务。"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.db.models import ChatMessage, ChatSession, User
from backend.infra.cache import cache


def create_session_id() -> str:
    """生成前端不可预测的聊天会话 ID。"""
    return uuid4().hex


def build_session_title(first_message: str) -> str:
    """根据首条用户消息生成简短会话标题。"""
    compact_title = " ".join(first_message.strip().split())
    if not compact_title:
        return "新会话"
    if len(compact_title) <= 32:
        return compact_title
    return f"{compact_title[:32]}..."


def get_session_title(session: ChatSession) -> str:
    """从会话元信息中读取标题，没有标题时返回默认标题。"""
    metadata = session.metadata_json or {}
    title = str(metadata.get("title") or "").strip()
    return title or "新会话"


def build_sessions_cache_key(user: User) -> str:
    """生成当前用户会话列表缓存 key。"""
    return f"chat:sessions:{user.username}"


def build_messages_cache_key(user: User, session_id: str) -> str:
    """生成当前用户指定会话消息缓存 key。"""
    return f"chat:messages:{user.username}:{session_id}"


def serialize_datetime(value: datetime) -> str:
    """将数据库时间转换为 JSON 可保存的字符串。"""
    return value.isoformat()


def serialize_message(message: ChatMessage) -> dict[str, Any]:
    """将数据库消息模型转换为缓存和接口共用的字典。"""
    return {
        "message_type": message.message_type,
        "content": message.content,
        "timestamp": serialize_datetime(message.timestamp),
        "rag_trace": message.rag_trace,
    }


def serialize_session_summary(session: ChatSession) -> dict[str, Any]:
    """将数据库会话模型转换为缓存和接口共用的摘要字典。"""
    return {
        "session_id": session.session_id,
        "title": get_session_title(session),
        "created_at": serialize_datetime(session.created_at),
        "updated_at": serialize_datetime(session.updated_at),
    }


def serialize_session_detail(session: ChatSession, messages: list[ChatMessage]) -> dict[str, Any]:
    """将数据库会话和消息列表转换为缓存和接口共用的详情字典。"""
    return {
        **serialize_session_summary(session),
        "messages": [serialize_message(message) for message in messages],
    }


def get_user_session(db_session: Session, user: User, session_id: str) -> ChatSession | None:
    """查询当前用户拥有的指定会话。"""
    return (
        db_session.query(ChatSession)
        .filter(ChatSession.user_id == user.id, ChatSession.session_id == session_id)
        .first()
    )


def list_user_sessions(db_session: Session, user: User) -> list[ChatSession]:
    """按更新时间倒序查询当前用户的会话列表。"""
    return (
        db_session.query(ChatSession)
        .filter(ChatSession.user_id == user.id)
        .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        .all()
    )


def list_user_session_summaries(db_session: Session, user: User) -> list[dict[str, Any]]:
    """优先从 Redis 读取当前用户会话列表，未命中时降级读取数据库。"""
    cache_key = build_sessions_cache_key(user)
    cached_sessions = cache.get_json(cache_key)
    if isinstance(cached_sessions, list):
        return cached_sessions

    sessions = list_user_sessions(db_session, user)
    payload = [serialize_session_summary(session) for session in sessions]
    cache.set_json(cache_key, payload)
    return payload


def list_session_messages(db_session: Session, session: ChatSession) -> list[ChatMessage]:
    """按创建顺序查询指定会话中的消息。"""
    return (
        db_session.query(ChatMessage)
        .filter(ChatMessage.session_ref_id == session.id)
        .order_by(ChatMessage.timestamp.asc(), ChatMessage.id.asc())
        .all()
    )


def get_session_detail_payload(db_session: Session, user: User, session_id: str) -> dict[str, Any] | None:
    """优先从 Redis 读取会话详情，未命中时降级读取数据库。"""
    clean_session_id = session_id.strip()
    cache_key = build_messages_cache_key(user, clean_session_id)
    cached_detail = cache.get_json(cache_key)
    if isinstance(cached_detail, dict):
        return cached_detail

    session = get_user_session(db_session, user, clean_session_id)
    if not session:
        return None

    messages = list_session_messages(db_session, session)
    payload = serialize_session_detail(session, messages)
    cache.set_json(cache_key, payload)
    return payload


def invalidate_session_cache(user: User, session_id: str | None = None) -> None:
    """删除当前用户的会话列表缓存和可选的会话详情缓存。"""
    cache.delete(build_sessions_cache_key(user))
    if session_id:
        cache.delete(build_messages_cache_key(user, session_id))


def save_chat_turn(
    db_session: Session,
    user: User,
    user_message: str,
    ai_message: str,
    session_id: str | None = None,
    rag_trace: dict | None = None,
) -> ChatSession:
    """保存一轮用户消息和 AI 回复，并返回所属会话。"""
    clean_session_id = (session_id or "").strip()
    session = get_user_session(db_session, user, clean_session_id) if clean_session_id else None
    if clean_session_id and session is None:
        raise LookupError("会话不存在")

    now = datetime.utcnow()
    if session is None:
        session = ChatSession(
            user_id=user.id,
            session_id=create_session_id(),
            metadata_json={"title": build_session_title(user_message)},
            created_at=now,
            updated_at=now,
        )
        db_session.add(session)
        db_session.flush()

    session.updated_at = now
    db_session.add(
        ChatMessage(
            session_ref_id=session.id,
            message_type="user",
            content=user_message,
            timestamp=now,
            rag_trace=None,
        )
    )
    db_session.add(
        ChatMessage(
            session_ref_id=session.id,
            message_type="ai",
            content=ai_message,
            timestamp=now,
            rag_trace=rag_trace,
        )
    )
    db_session.commit()
    db_session.refresh(session)
    invalidate_session_cache(user, session.session_id)
    return session
