"""KnowMind 文档上传接口路由。"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.api.resources import (
    UploadTooLargeError,
    UploadValidationError,
    build_upload_path,
    normalize_upload_filename,
    save_upload_file,
)
from backend.db.models import User
from backend.infra.auth import require_admin
from backend.schemas.documents import DocumentUploadResponse


router = APIRouter(tags=["documents"])


@router.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    _admin: User = Depends(require_admin),
) -> DocumentUploadResponse:
    """保存管理员上传的 PDF 文件，暂不执行解析和分块。"""
    try:
        filename = normalize_upload_filename(file.filename)
        target_path = build_upload_path(filename)
        await save_upload_file(file, target_path)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文件保存失败") from exc

    return DocumentUploadResponse(
        filename=filename,
        chunks_processed=0,
        message=f"成功上传 {filename}，等待后续解析",
    )
