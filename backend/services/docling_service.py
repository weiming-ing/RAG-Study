import io
import os
import time
import tempfile
import logging
import threading
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("docling_service")

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".txt", ".md", ".html", ".htm", ".rtf", ".csv", ".xml"}
MAX_FILE_SIZE = 50 * 1024 * 1024
PARSE_TIMEOUT_SECONDS = 60


class DoclingParseError(Exception):
    pass


class DoclingService:
    """
    文档统一解析服务（基于 IBM Docling）

    职责：将上传文件转为结构化 Markdown，保留：
      - 标题层级（# / ## / ###）
      - 表格（Markdown 表格格式）
      - 列表、加粗等富文本结构
      - 页码分段

    初始化在 FastAPI 启动时异步完成，避免阻塞首次上传请求。
    上游：routes/knowledge.py 的上传接口
    下游：解析后的 Markdown 以 content 字段传给 Java 后端，替代原有 Tika 纯文本提取
    """

    _converter = None
    _initialized = False
    _init_error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self._initialized

    def init_background(self):
        """在后台线程中初始化 Docling DocumentConverter，避免阻塞事件循环"""
        if self._initialized:
            return
        try:
            from docling.document_converter import DocumentConverter
            self._converter = DocumentConverter()
            self._initialized = True
            self._init_error = None
            logger.info("Docling DocumentConverter 初始化成功")
        except ImportError:
            self._init_error = "docling 未安装，请运行: pip install docling>=2.0"
            logger.warning("Docling 初始化失败: %s", self._init_error)
        except Exception as e:
            self._init_error = str(e)
            logger.warning("Docling 初始化失败: %s", e)

    def _ensure_initialized(self):
        if self._initialized:
            return
        if self._init_error:
            raise DoclingParseError(self._init_error)
        raise DoclingParseError("Docling 尚未完成初始化，请稍后重试")

    def supports(self, filename: str) -> bool:
        ext = os.path.splitext(filename or "")[1].lower()
        return ext in SUPPORTED_EXTENSIONS

    def parse_to_markdown(
        self,
        file_bytes: bytes,
        filename: str,
        file_type: Optional[str] = None,
    ) -> Tuple[str, dict]:
        """
        将文件字节流转为结构化 Markdown

        Args:
            file_bytes: 文件原始字节
            filename: 原始文件名（用于推断格式）
            file_type: MIME 类型（可选，用于辅助推断）

        Returns:
            (markdown_text, metadata) 其中 metadata 包含:
                - format: 文件格式
                - pages: 页码数（PDF）
                - tables_count: 表格数量
                - parse_time_ms: 解析耗时

        Raises:
            DoclingParseError: 解析失败或格式不支持
        """
        if len(file_bytes) > MAX_FILE_SIZE:
            raise DoclingParseError(f"文件大小 {len(file_bytes)} 字节超过限制 {MAX_FILE_SIZE} 字节")

        ext = os.path.splitext(filename or "")[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise DoclingParseError(f"不支持的文件格式: {ext}")

        self._ensure_initialized()

        t_start = time.time()
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=ext, delete=False, dir=tempfile.gettempdir()
            ) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            result = self._converter.convert(tmp_path)
            markdown = result.document.export_to_markdown()

            metadata = {
                "format": ext.lstrip("."),
                "tables_count": len(result.document.tables) if hasattr(result.document, "tables") else 0,
                "parse_time_ms": int((time.time() - t_start) * 1000),
                "markdown_length": len(markdown),
                "original_bytes": len(file_bytes),
            }
            logger.info(
                "Docling 解析完成: %s → %d 字 (%d 表格, %dms)",
                filename, len(markdown), metadata["tables_count"], metadata["parse_time_ms"],
            )
            return markdown, metadata

        except DoclingParseError:
            raise
        except Exception as e:
            raise DoclingParseError(f"文档解析失败 ({filename}): {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def parse_to_markdown_sync(
        self, file_bytes: bytes, filename: str, file_type: Optional[str] = None
    ) -> Tuple[str, dict]:
        return self.parse_to_markdown(file_bytes, filename, file_type)


docling_service = DoclingService()