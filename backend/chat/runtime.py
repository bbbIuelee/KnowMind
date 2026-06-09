"""KnowMind 聊天模型运行时。"""

import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any

from backend.env import load_env


SYSTEM_PROMPT = (
    "你是 KnowMind 知识库问答助手。"
    "当前阶段只进行普通对话，不调用知识库、不编造检索来源。"
    "请用清晰、简洁、可靠的中文回答用户问题。"
)
DEFAULT_TIMEOUT_SECONDS = 60


class ChatRuntimeError(RuntimeError):
    """聊天运行时异常基类。"""


class ChatConfigError(ChatRuntimeError):
    """聊天模型配置缺失或无效时抛出的异常。"""


class ChatUpstreamError(ChatRuntimeError):
    """模型服务调用失败时抛出的异常。"""


def _get_required_env(name: str) -> str:
    """读取必填环境变量并去除首尾空白。"""
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ChatConfigError(f"模型配置缺失：请在 .env 中配置 {name}")
    return value


def _get_timeout_seconds() -> int:
    """读取模型请求超时时间配置。"""
    raw_value = (os.getenv("CHAT_TIMEOUT_SECONDS") or "").strip()
    if not raw_value:
        return DEFAULT_TIMEOUT_SECONDS

    try:
        timeout_seconds = int(raw_value)
    except ValueError as exc:
        raise ChatConfigError("模型配置无效：CHAT_TIMEOUT_SECONDS 必须是整数") from exc

    if timeout_seconds <= 0:
        raise ChatConfigError("模型配置无效：CHAT_TIMEOUT_SECONDS 必须大于 0")
    return timeout_seconds


def _build_chat_completions_url(base_url: str) -> str:
    """根据 OpenAI 兼容基础地址生成聊天补全接口地址。"""
    normalized_base_url = base_url.rstrip("/")
    if normalized_base_url.endswith("/chat/completions"):
        return normalized_base_url
    return f"{normalized_base_url}/chat/completions"


def _read_error_body(response: urllib.error.HTTPError) -> str:
    """读取上游错误响应，并提取适合返回给前端的摘要。"""
    raw_body = response.read().decode("utf-8", errors="replace").strip()
    if not raw_body:
        return "模型服务没有返回错误详情"

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return raw_body[:300]

    error_info = payload.get("error")
    if isinstance(error_info, dict):
        message = error_info.get("message")
        if message:
            return str(message)[:300]
    if isinstance(error_info, str):
        return error_info[:300]
    return raw_body[:300]


def _extract_response_content(payload: dict[str, Any]) -> str:
    """从 OpenAI 兼容响应中提取模型回答文本。"""
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ChatUpstreamError("模型服务响应缺少 choices 字段")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ChatUpstreamError("模型服务响应 choices 格式无效")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ChatUpstreamError("模型服务响应缺少 message 字段")

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()
    raise ChatUpstreamError("模型服务返回了空回答")


def chat_with_model(user_message: str) -> str:
    """调用兼容 OpenAI 协议的大模型，返回非流式普通对话结果。"""
    load_env()

    api_key = _get_required_env("ARK_API_KEY")
    model = _get_required_env("MODEL")
    base_url = _get_required_env("BASE_URL")
    timeout_seconds = _get_timeout_seconds()
    chat_url = _build_chat_completions_url(base_url)

    request_body = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
    }
    request = urllib.request.Request(
        chat_url,
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_detail = _read_error_body(exc)
        raise ChatUpstreamError(f"模型服务请求失败（HTTP {exc.code}）：{error_detail}") from exc
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise ChatUpstreamError(f"无法连接模型服务：{exc}") from exc

    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError as exc:
        raise ChatUpstreamError("模型服务响应不是有效 JSON") from exc
    return _extract_response_content(payload)
