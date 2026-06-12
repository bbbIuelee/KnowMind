"""KnowMind 非流式聊天接口路由。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.chat.storage import (
    get_session_detail_payload,
    get_user_session,
    list_user_session_summaries,
    save_chat_turn,
)
from backend.chat.runtime import ChatConfigError, ChatRuntimeError, chat_with_model
from backend.db.models import User
from backend.infra.auth import get_current_user
from backend.infra.database import get_db_session
from backend.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatSessionDetailResponse,
    ChatSessionSummaryResponse,
)


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat_once(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ChatResponse:
    """调用真实大模型，按当前用户和会话保存一轮聊天消息。"""
    clean_message = request.message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    clean_session_id = (request.session_id or "").strip() or None
    if clean_session_id and not get_user_session(db_session, current_user, clean_session_id):
        raise HTTPException(status_code=404, detail="会话不存在")

    try:
        reply = chat_with_model(clean_message)
    except ChatConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ChatRuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    session = save_chat_turn(
        db_session=db_session,
        user=current_user,
        user_message=clean_message,
        ai_message=reply,
        session_id=clean_session_id,
        rag_trace=None,
    )
    return ChatResponse(session_id=session.session_id, response=reply, rag_trace=None)


@router.get("/sessions", response_model=list[ChatSessionSummaryResponse])
def get_sessions(
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> list[ChatSessionSummaryResponse]:
    """返回当前用户可见的会话列表。"""
    sessions = list_user_session_summaries(db_session, current_user)
    return [ChatSessionSummaryResponse(**session) for session in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionDetailResponse)
def get_session_detail(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db_session: Session = Depends(get_db_session),
) -> ChatSessionDetailResponse:
    """返回当前用户拥有的指定会话详情。"""
    detail = get_session_detail_payload(db_session, current_user, session_id)
    if not detail:
        raise HTTPException(status_code=404, detail="会话不存在")

    return ChatSessionDetailResponse(**detail)
