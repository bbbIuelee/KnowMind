"""KnowMind 文档接口响应模型。"""

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """文档上传响应模型，描述文档解析和向量入库结果。"""

    filename: str = Field(..., description="保存后的文件名")
    chunks_processed: int = Field(..., description="当前阶段处理的分块数量")
    message: str = Field(..., description="上传结果说明")
