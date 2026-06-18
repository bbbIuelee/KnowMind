"""KnowMind 文档上传接口路由。"""

import asyncio

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.api.resources import (
    UploadTooLargeError,
    UploadValidationError,
    build_upload_path,
    document_loader,
    milvus_writer,
    normalize_upload_filename,
    parent_chunk_store,
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
    """保存管理员上传的文档，并写入父级分块和 L3 稠密向量。"""
    target_path = None
    try:
        filename = normalize_upload_filename(file.filename)
        target_path = build_upload_path(filename)
        await save_upload_file(file, target_path)
        chunks = await asyncio.to_thread(document_loader.load_document, target_path, filename)
        leaf_chunks = [chunk for chunk in chunks if int(chunk.get("chunk_level") or 0) == 3]
        if not leaf_chunks:
            raise ValueError("文档未生成可检索的 L3 叶子分块")

        await asyncio.to_thread(parent_chunk_store.delete_by_filename, filename)
        parent_count = await asyncio.to_thread(parent_chunk_store.upsert_documents, chunks)
        leaf_count = await asyncio.to_thread(
            milvus_writer.replace_documents,
            filename,
            leaf_chunks,
        )
        if leaf_count != len(leaf_chunks):
            raise RuntimeError(
                f"Milvus 写入数量不匹配：期望 {len(leaf_chunks)}，实际 {leaf_count}"
            )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc)) from exc
    except UploadValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except ValueError as exc:
        if target_path is not None and target_path.exists():
            target_path.unlink()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文件保存失败") from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文档入库失败") from exc

    return DocumentUploadResponse(
        filename=filename,
        chunks_processed=leaf_count,
        message=f"成功上传并处理 {filename}，父级分块 {parent_count} 个，L3 向量 {leaf_count} 个",
    )
