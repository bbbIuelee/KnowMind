"""KnowMind 非流式聊天接口路由。"""

from fastapi import APIRouter

from backend.schemas.chat import ChatRequest, ChatResponse


router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
def chat_once(request: ChatRequest) -> ChatResponse:
    """返回 Day 04 阶段的非流式假数据聊天回复。"""
    clean_message = request.message.strip()
    reply = (
        f"已收到你的问题：{clean_message}。"
        "当前是 Day 04 的非流式聊天接口假数据回复，下一阶段会接入真实大模型。"
    )
    return ChatResponse(response=reply, rag_trace=None)
