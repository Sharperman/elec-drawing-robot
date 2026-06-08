"""
KnowledgeDocument 数据模型
存储用户上传的知识文档（设计手册、规程、策划文件等），
与 OCR 后的分块结果关联，供 RAG 检索使用。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Float, Index,
)
from sqlalchemy.sql import func

from models.session import Base


class KnowledgeDocument(Base):
    """
    知识文档表

    记录每个上传文档的元数据和处理状态。
    实际文本分块存储在 ChromaDB user_knowledge collection 中。
    """
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # ── 文件信息 ──────────────────────────────
    filename = Column(String(500), nullable=False, comment="原始文件名")
    stored_path = Column(String(1000), nullable=False, comment="存储路径")
    file_type = Column(String(20), nullable=False, comment="文件类型: pdf/docx/pptx/image/txt")
    file_size = Column(Integer, default=0, comment="文件大小 (bytes)")
    page_count = Column(Integer, default=0, comment="总页数")
    doc_category = Column(String(100), comment="文档分类: 设计手册/规程/策划文件/厂家资料/其他")

    # ── 处理状态 ──────────────────────────────
    # pending → extracting → ocr → quality_check → chunking → embedding → ready
    # 任意步骤失败 → error
    processing_status = Column(
        String(30), default="pending",
        comment="pending/extracting/ocr/quality_check/chunking/embedding/ready/error"
    )
    processing_error = Column(Text, comment="处理错误信息")

    # ── 处理结果 ──────────────────────────────
    chunk_count = Column(Integer, default=0, comment="分块数量")
    total_tokens = Column(Integer, default=0, comment="总 token 估算")
    ocr_engine = Column(String(30), comment="使用的 OCR 引擎: native/paddle/l3_vision")
    quality_score = Column(Float, comment="质量评分 0-1，由 LLM 判断")
    quality_notes = Column(Text, comment="质量评估备注")
    has_latex = Column(Boolean, default=False, comment="文档是否包含 LaTeX 公式")
    image_count = Column(Integer, default=0, comment="提取的图片数量")
    table_count = Column(Integer, default=0, comment="提取的表格数量")

    # ── 元数据 ──────────────────────────────
    is_active = Column(Boolean, default=True, comment="是否启用")
    tags = Column(Text, comment="用户标签 (JSON 数组)")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_kdoc_status", "processing_status"),
        Index("idx_kdoc_active", "is_active"),
        Index("idx_kdoc_category", "doc_category"),
    )

    def to_dict(self) -> dict:
        import json
        tags = []
        if self.tags:
            try:
                tags = json.loads(self.tags)
            except Exception:
                pass
        return {
            "id": self.id,
            "filename": self.filename,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "page_count": self.page_count,
            "doc_category": self.doc_category,
            "processing_status": self.processing_status,
            "processing_error": self.processing_error,
            "chunk_count": self.chunk_count,
            "total_tokens": self.total_tokens,
            "ocr_engine": self.ocr_engine,
            "quality_score": self.quality_score,
            "quality_notes": self.quality_notes,
            "has_latex": self.has_latex,
            "image_count": self.image_count,
            "table_count": self.table_count,
            "is_active": self.is_active,
            "tags": tags,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
