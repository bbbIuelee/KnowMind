"""KnowMind 后端环境配置加载模块。"""

from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

_LOADED = False


def load_env() -> None:
    """从项目根目录按 UTF-8 编码加载 .env 文件。"""
    global _LOADED
    if _LOADED:
        return

    load_dotenv(ENV_FILE, encoding="utf-8")
    _LOADED = True
