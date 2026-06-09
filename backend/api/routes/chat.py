"""KnowMind 非流式聊天接口路由。"""

from fastapi import APIRouter, HTTPException

from backend.chat.runtime import ChatConfigError, ChatRuntimeError, chat_with_model
from backend.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat_once(request: ChatRequest) -> ChatResponse:
    """调用真实大模型并返回非流式聊天回复。"""
    clean_message = request.message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    try:
        reply = chat_with_model(clean_message)
    except ChatConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ChatRuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ChatResponse(response=reply, rag_trace=None)
