"""KnowMind API 资源和文件上传辅助函数。"""

import os
import re
from pathlib import Path

from fastapi import UploadFile

from backend.env import PROJECT_ROOT, load_env


load_env()

DATA_DIR = PROJECT_ROOT / "data"
UPLOAD_DIR = DATA_DIR / "documents"
UPLOAD_CHUNK_SIZE = 1024 * 1024
MAX_UPLOAD_BYTES = int(os.getenv("DOCUMENT_UPLOAD_MAX_BYTES", str(20 * 1024 * 1024)))
SUPPORTED_DOCUMENT_SUFFIXES = {".pdf", ".docx", ".xlsx"}


class UploadValidationError(ValueError):
    """上传文件参数不合法时抛出的异常。"""


class UploadTooLargeError(ValueError):
    """上传文件超过大小限制时抛出的异常。"""


def ensure_upload_dir() -> None:
    """确保文档上传目录存在。"""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def is_supported_document(filename: str) -> bool:
    """判断当前阶段是否支持该文件类型。"""
    return Path(filename).suffix.lower() in SUPPORTED_DOCUMENT_SUFFIXES


def normalize_upload_filename(raw_filename: str | None) -> str:
    """清理上传文件名，避免路径穿越和非法字符。"""
    filename = (raw_filename or "").replace("\\", "/").split("/")[-1].strip()
    if not filename or filename in {".", ".."}:
        raise UploadValidationError("文件名不能为空")

    safe_filename = re.sub(r"[^0-9A-Za-z._\-\u4e00-\u9fff]", "_", filename)
    if not safe_filename or safe_filename.startswith("."):
        raise UploadValidationError("文件名不合法")
    if not is_supported_document(safe_filename):
        raise UploadValidationError("当前阶段仅支持 PDF、DOCX 和 XLSX 文件")
    return safe_filename


def build_upload_path(filename: str) -> Path:
    """根据安全文件名构建上传保存路径。"""
    ensure_upload_dir()
    upload_root = UPLOAD_DIR.resolve()
    target_path = (upload_root / filename).resolve()
    if target_path.parent != upload_root:
        raise UploadValidationError("文件路径不合法")
    return target_path


async def save_upload_file(file: UploadFile, target_path: Path) -> int:
    """按块保存上传文件，并返回写入字节数。"""
    total_bytes = 0
    try:
        with target_path.open("wb") as output_file:
            while True:
                chunk = await file.read(UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break

                total_bytes += len(chunk)
                if total_bytes > MAX_UPLOAD_BYTES:
                    raise UploadTooLargeError("文件大小超过限制")

                output_file.write(chunk)
    except Exception:
        if target_path.exists():
            target_path.unlink()
        raise
    finally:
        await file.close()

    return total_bytes
