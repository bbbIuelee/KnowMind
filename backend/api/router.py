"""KnowMind 后端 API 路由聚合模块。"""

from fastapi import APIRouter

from backend.api.routes.chat import router as chat_router


router = APIRouter()
router.include_router(chat_router)


@router.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    """返回 KnowMind 服务健康检查信息。"""
    return {"status": "ok", "service": "knowmind"}
