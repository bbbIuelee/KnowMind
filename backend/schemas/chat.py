"""KnowMind 聊天接口请求和响应模型。"""

from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求模型，描述前端提交的单轮用户消息。"""

    message: str = Field(..., min_length=1, description="用户输入的消息内容")
    session_id: str | None = Field(default=None, description="可选的会话 ID")


class ChatResponse(BaseModel):
    """聊天响应模型，描述后端返回给前端的非流式回答。"""

    response: str = Field(..., description="AI 回复内容")
    rag_trace: dict[str, Any] | None = Field(default=None, description="RAG 追踪信息")
