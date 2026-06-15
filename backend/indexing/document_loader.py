"""KnowMind 文档解析和三级分块模块。"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from docx import Document as DocxDocument
from openpyxl import load_workbook
from pypdf import PdfReader


DEFAULT_LEVEL_1_SIZE = 2400
DEFAULT_LEVEL_1_OVERLAP = 300
DEFAULT_LEVEL_2_SIZE = 1200
DEFAULT_LEVEL_2_OVERLAP = 160
DEFAULT_LEVEL_3_SIZE = 600
DEFAULT_LEVEL_3_OVERLAP = 80
SPLIT_SEPARATORS = ["\n\n", "。", "！", "？", "\n", "，", "、", " ", ""]


@dataclass
class RawDocumentPage:
    """原始文档页模型，保存页号和提取出的文本。"""

    page_number: int
    text: str


class DocumentLoader:
    """文档解析器，负责提取文本并输出 L1/L2/L3 三级分块。"""

    def __init__(
        self,
        level_1_size: int = DEFAULT_LEVEL_1_SIZE,
        level_1_overlap: int = DEFAULT_LEVEL_1_OVERLAP,
        level_2_size: int = DEFAULT_LEVEL_2_SIZE,
        level_2_overlap: int = DEFAULT_LEVEL_2_OVERLAP,
        level_3_size: int = DEFAULT_LEVEL_3_SIZE,
        level_3_overlap: int = DEFAULT_LEVEL_3_OVERLAP,
    ) -> None:
        """初始化三级分块大小和重叠长度。"""
        self.level_1_size = level_1_size
        self.level_1_overlap = level_1_overlap
        self.level_2_size = level_2_size
        self.level_2_overlap = level_2_overlap
        self.level_3_size = level_3_size
        self.level_3_overlap = level_3_overlap

    def _normalize_text(self, text: str) -> str:
        """清理多余空白，保留段落边界。"""
        lines = [line.strip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
        return "\n".join(line for line in lines if line).strip()

    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int) -> list[str]:
        """按分隔符优先级把文本切成固定上限的片段。"""
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            return []
        if len(normalized_text) <= chunk_size:
            return [normalized_text]

        chunks: list[str] = []
        cursor = 0
        safe_overlap = max(0, min(chunk_overlap, chunk_size - 1))

        while cursor < len(normalized_text):
            end = min(cursor + chunk_size, len(normalized_text))
            if end < len(normalized_text):
                split_at = self._find_split_position(normalized_text, cursor, end)
                if split_at > cursor:
                    end = split_at

            chunk = normalized_text[cursor:end].strip()
            if chunk:
                chunks.append(chunk)
            if end >= len(normalized_text):
                break
            cursor = max(end - safe_overlap, cursor + 1)

        return chunks

    def _find_split_position(self, text: str, start: int, end: int) -> int:
        """在窗口内寻找最适合切分的位置。"""
        window = text[start:end]
        minimum_tail = max(80, (end - start) // 5)
        for separator in SPLIT_SEPARATORS:
            if not separator:
                continue
            position = window.rfind(separator)
            if position >= minimum_tail:
                return start + position + len(separator)
        return end

    def _build_chunk_id(self, filename: str, page_number: int, level: int, index: int) -> str:
        """生成可追踪的 chunk ID。"""
        return f"{filename}::p{page_number}::l{level}::{index}"

    def _build_base_metadata(
        self,
        file_path: Path,
        filename: str,
        file_type: str,
        page: RawDocumentPage,
    ) -> dict[str, Any]:
        """生成分块通用 metadata。"""
        return {
            "filename": filename,
            "file_type": file_type,
            "file_path": str(file_path),
            "page_number": page.page_number,
        }

    def _split_page_to_three_levels(
        self,
        page: RawDocumentPage,
        base_metadata: dict[str, Any],
        start_chunk_idx: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """将单页文本切分为 L1、L2、L3 三级 chunk。"""
        chunks: list[dict[str, Any]] = []
        next_chunk_idx = start_chunk_idx
        filename = str(base_metadata["filename"])
        page_number = int(base_metadata["page_number"])

        level_1_chunks = self._split_text(page.text, self.level_1_size, self.level_1_overlap)
        level_2_counter = 0
        level_3_counter = 0

        for level_1_index, level_1_text in enumerate(level_1_chunks):
            level_1_id = self._build_chunk_id(filename, page_number, 1, level_1_index)
            chunks.append(
                {
                    **base_metadata,
                    "text": level_1_text,
                    "chunk_id": level_1_id,
                    "parent_chunk_id": "",
                    "root_chunk_id": level_1_id,
                    "chunk_level": 1,
                    "chunk_idx": next_chunk_idx,
                }
            )
            next_chunk_idx += 1

            level_2_chunks = self._split_text(level_1_text, self.level_2_size, self.level_2_overlap)
            for level_2_text in level_2_chunks:
                level_2_id = self._build_chunk_id(filename, page_number, 2, level_2_counter)
                level_2_counter += 1
                chunks.append(
                    {
                        **base_metadata,
                        "text": level_2_text,
                        "chunk_id": level_2_id,
                        "parent_chunk_id": level_1_id,
                        "root_chunk_id": level_1_id,
                        "chunk_level": 2,
                        "chunk_idx": next_chunk_idx,
                    }
                )
                next_chunk_idx += 1

                level_3_chunks = self._split_text(level_2_text, self.level_3_size, self.level_3_overlap)
                for level_3_text in level_3_chunks:
                    level_3_id = self._build_chunk_id(filename, page_number, 3, level_3_counter)
                    level_3_counter += 1
                    chunks.append(
                        {
                            **base_metadata,
                            "text": level_3_text,
                            "chunk_id": level_3_id,
                            "parent_chunk_id": level_2_id,
                            "root_chunk_id": level_1_id,
                            "chunk_level": 3,
                            "chunk_idx": next_chunk_idx,
                        }
                    )
                    next_chunk_idx += 1

        return chunks, next_chunk_idx

    def _load_pdf_pages(self, file_path: Path) -> list[RawDocumentPage]:
        """读取 PDF 每页文本。"""
        reader = PdfReader(str(file_path))
        pages: list[RawDocumentPage] = []
        for index, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append(RawDocumentPage(page_number=index, text=text))
        return pages

    def _load_docx_pages(self, file_path: Path) -> list[RawDocumentPage]:
        """读取 DOCX 文档文本。"""
        document = DocxDocument(str(file_path))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        table_rows: list[str] = []
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    table_rows.append(" | ".join(cells))
        text = "\n".join([*paragraphs, *table_rows])
        return [RawDocumentPage(page_number=0, text=text)]

    def _load_xlsx_pages(self, file_path: Path) -> list[RawDocumentPage]:
        """读取 XLSX 每个工作表的文本。"""
        workbook = load_workbook(filename=str(file_path), read_only=True, data_only=True)
        pages: list[RawDocumentPage] = []
        try:
            for sheet_index, sheet in enumerate(workbook.worksheets):
                lines: list[str] = []
                for row in sheet.iter_rows(values_only=True):
                    values = [str(value).strip() for value in row if value is not None and str(value).strip()]
                    if values:
                        lines.append(" | ".join(values))
                pages.append(RawDocumentPage(page_number=sheet_index, text="\n".join(lines)))
        finally:
            workbook.close()
        return pages

    def _load_raw_pages(self, file_path: Path, filename: str) -> tuple[str, list[RawDocumentPage]]:
        """按文件后缀读取原始页面文本。"""
        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            return "PDF", self._load_pdf_pages(file_path)
        if suffix == ".docx":
            return "Word", self._load_docx_pages(file_path)
        if suffix == ".xlsx":
            return "Excel", self._load_xlsx_pages(file_path)
        raise ValueError(f"不支持的文件类型: {filename}")

    def load_document(self, file_path: str | Path, filename: str | None = None) -> list[dict[str, Any]]:
        """解析单个文档并返回三级分块结果。"""
        path = Path(file_path)
        resolved_filename = filename or path.name
        file_type, pages = self._load_raw_pages(path, resolved_filename)

        all_chunks: list[dict[str, Any]] = []
        next_chunk_idx = 0
        for page in pages:
            if not self._normalize_text(page.text):
                continue
            base_metadata = self._build_base_metadata(path, resolved_filename, file_type, page)
            page_chunks, next_chunk_idx = self._split_page_to_three_levels(
                page=page,
                base_metadata=base_metadata,
                start_chunk_idx=next_chunk_idx,
            )
            all_chunks.extend(page_chunks)

        if not all_chunks:
            raise ValueError("文档未提取到可分块文本")
        return all_chunks

    def load_documents_from_folder(self, folder_path: str | Path) -> list[dict[str, Any]]:
        """解析目录下所有支持的文档并合并返回分块结果。"""
        folder = Path(folder_path)
        all_chunks: list[dict[str, Any]] = []
        for file_path in sorted(folder.iterdir()):
            if not file_path.is_file():
                continue
            try:
                all_chunks.extend(self.load_document(file_path, file_path.name))
            except ValueError:
                continue
        return all_chunks
