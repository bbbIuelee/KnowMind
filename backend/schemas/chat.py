"""KnowMind 聊天接口和会话接口请求响应模型。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """聊天请求模型，描述前端提交的单轮用户消息。"""

    message: str = Field(..., min_length=1, description="用户输入的消息内容")
    session_id: str | None = Field(default=None, description="可选的会话 ID")


class ChatResponse(BaseModel):
    """聊天响应模型，描述后端返回给前端的非流式回答和会话 ID。"""

    session_id: str = Field(..., description="本轮聊天所属的会话 ID")
    response: str = Field(..., description="AI 回复内容")
    rag_trace: dict[str, Any] | None = Field(default=None, description="RAG 追踪信息")


class ChatMessageResponse(BaseModel):
    """会话消息响应模型，描述一条用户消息或 AI 消息。"""

    message_type: str = Field(..., description="消息类型，user 表示用户，ai 表示模型")
    content: str = Field(..., description="消息正文")
    timestamp: datetime = Field(..., description="消息创建时间")
    rag_trace: dict[str, Any] | None = Field(default=None, description="RAG 追踪信息")


class ChatSessionSummaryResponse(BaseModel):
    """会话摘要响应模型，描述会话列表中的单个会话。"""

    session_id: str = Field(..., description="会话 ID")
    title: str = Field(..., description="会话标题")
    created_at: datetime = Field(..., description="会话创建时间")
    updated_at: datetime = Field(..., description="会话最近更新时间")


class ChatSessionDetailResponse(ChatSessionSummaryResponse):
    """会话详情响应模型，描述会话元信息和消息列表。"""

    messages: list[ChatMessageResponse] = Field(default_factory=list, description="会话消息列表")
