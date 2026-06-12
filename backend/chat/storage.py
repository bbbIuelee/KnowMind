"""KnowMind 聊天会话持久化存储服务。"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.db.models import ChatMessage, ChatSession, User


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


def list_session_messages(db_session: Session, session: ChatSession) -> list[ChatMessage]:
    """按创建顺序查询指定会话中的消息。"""
    return (
        db_session.query(ChatMessage)
        .filter(ChatMessage.session_ref_id == session.id)
        .order_by(ChatMessage.timestamp.asc(), ChatMessage.id.asc())
        .all()
    )


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
    return session
