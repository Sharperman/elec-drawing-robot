"""
知识库 API 路由
POST   /api/knowledge/upload              — 上传文档（支持批量）
GET    /api/knowledge/documents            — 文档列表
GET    /api/knowledge/documents/{id}       — 文档详情
DELETE /api/knowledge/documents/{id}       — 删除文档
POST   /api/knowledge/documents/{id}/reprocess — 重新处理
GET    /api/knowledge/search               — 语义搜索
"""
import json
import os
import uuid
from pathlib import Path
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from loguru import logger
from sqlalchemy.orm import Session
from sqlalchemy import desc

from models.session import get_db
from models.knowledge_document import KnowledgeDocument
from api.schemas import ApiResponse
from config import settings

router = APIRouter()

# 知识文档上传目录
KNOWLEDGE_UPLOAD_DIR = Path("data/uploads/knowledge")
KNOWLEDGE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ── 上传文档 ───────────────────────────────────────────

@router.post("/upload", response_model=ApiResponse)
async def upload_knowledge_documents(
    files: List[UploadFile] = File(...),
    doc_category: str = Query("其他", description="文档分类"),
    db: Session = Depends(get_db),
):
    """
    上传知识文档（支持批量）。
    上传后自动触发后台处理管道：提取 → OCR → 质量检查 → 分块 → 向量化。
    """
    uploaded = []
    for file in files:
        if not file.filename:
            continue

        ext = Path(file.filename).suffix.lower().lstrip(".")
        file_type = ext if ext in ("pdf", "docx", "pptx", "txt", "jpg", "jpeg", "png", "bmp", "tiff") else "unknown"
        if file_type == "unknown":
            uploaded.append({"filename": file.filename, "status": "skipped", "reason": "不支持的文件类型"})
            continue

        # 检查文件大小
        contents = await file.read()
        file_size = len(contents)
        if file_type == "pdf" and file_size > 200 * 1024 * 1024:
            uploaded.append({"filename": file.filename, "status": "skipped", "reason": "PDF 超过 200MB 限制"})
            continue

        # 存储文件
        stored_name = f"{uuid.uuid4().hex[:12]}_{file.filename}"
        stored_path = KNOWLEDGE_UPLOAD_DIR / stored_name
        stored_path.write_bytes(contents)

        # 创建数据库记录
        doc = KnowledgeDocument(
            filename=file.filename,
            stored_path=str(stored_path),
            file_type=file_type,
            file_size=file_size,
            doc_category=doc_category,
            processing_status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        # 异步处理（后台线程）
        _process_document_async(doc.id, str(stored_path), file_type)
        uploaded.append({"filename": file.filename, "status": "accepted", "doc_id": doc.id})

    return ApiResponse(data={"uploaded": uploaded, "count": len(uploaded)})


# ── 文档列表 ───────────────────────────────────────────

@router.get("/documents", response_model=ApiResponse)
def list_knowledge_documents(
    status_filter: Optional[str] = Query(None, alias="status"),
    category_filter: Optional[str] = Query(None, alias="category"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """列出所有知识文档，支持按状态/分类过滤"""
    q = db.query(KnowledgeDocument)
    if status_filter:
        q = q.filter(KnowledgeDocument.processing_status == status_filter)
    if category_filter:
        q = q.filter(KnowledgeDocument.doc_category == category_filter)

    total = q.count()
    docs = q.order_by(desc(KnowledgeDocument.created_at)).offset((page - 1) * page_size).limit(page_size).all()

    return ApiResponse(data={
        "items": [d.to_dict() for d in docs],
        "total": total,
        "page": page,
        "page_size": page_size,
    })


# ── 文档详情 ───────────────────────────────────────────

@router.get("/documents/{doc_id}", response_model=ApiResponse)
def get_knowledge_document(doc_id: int, db: Session = Depends(get_db)):
    """获取单个文档详情"""
    doc = db.query(KnowledgeDocument).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return ApiResponse(data=doc.to_dict())


@router.get("/documents/{doc_id}/chunks", response_model=ApiResponse)
def get_document_chunks(doc_id: int, db: Session = Depends(get_db)):
    """获取文档的所有分块内容（含图片/表格/公式 metadata）"""
    doc = db.query(KnowledgeDocument).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    from knowledge.vector_store import vector_store
    vector_store._ensure_initialized()
    chunks = vector_store.get_chunks_by_doc(doc_id)

    # 从 metadata 中解析图片和表格信息
    images = []
    tables = []
    latex_formulas = []

    for c in chunks:
        meta = c.get("metadata", {})
        if meta.get("images"):
            try:
                imgs = json.loads(meta["images"])
                images.extend(imgs)
            except Exception:
                pass
        if meta.get("tables_preview"):
            try:
                tabs = json.loads(meta["tables_preview"])
                tables.extend(tabs)
            except Exception:
                pass

    # 检测 LaTeX 公式
    from knowledge.document_processor import detect_latex
    all_text = "\n".join(c["text"] for c in chunks[:10])
    latex_info = detect_latex(all_text)

    return ApiResponse(data={
        "chunks": [{"index": i, "text": c["text"][:500], "metadata": c["metadata"]} for i, c in enumerate(chunks[:50])],
        "images": images,
        "tables": tables[:10],
        "has_latex": latex_info["has_latex"],
        "latex_count": latex_info["count"],
        "total_chunks": len(chunks),
    })


# ── 删除文档 ───────────────────────────────────────────

@router.delete("/documents/{doc_id}", response_model=ApiResponse)
def delete_knowledge_document(doc_id: int, db: Session = Depends(get_db)):
    """删除文档及所有关联的向量 chunk"""
    doc = db.query(KnowledgeDocument).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    # 删除 ChromaDB 中的 chunk
    try:
        from knowledge.chunker import knowledge_embedder
        knowledge_embedder.delete_document_chunks(doc_id)
    except Exception as e:
        logger.warning(f"删除向量 chunk 失败: {e}")

    # 删除文件
    try:
        if doc.stored_path and os.path.exists(doc.stored_path):
            os.unlink(doc.stored_path)
    except Exception:
        pass

    db.delete(doc)
    db.commit()
    return ApiResponse(data={"deleted": doc_id})


# ── 重新处理 ───────────────────────────────────────────

@router.post("/documents/{doc_id}/reprocess", response_model=ApiResponse)
def reprocess_document(doc_id: int, db: Session = Depends(get_db)):
    """重新处理文档（覆盖旧版本）"""
    doc = db.query(KnowledgeDocument).filter_by(id=doc_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")

    doc.processing_status = "pending"
    doc.processing_error = None
    doc.chunk_count = 0
    db.commit()

    _process_document_async(doc_id, doc.stored_path, doc.file_type)
    return ApiResponse(data={"doc_id": doc_id, "status": "reprocessing"})


# ── 搜索 ───────────────────────────────────────────────

@router.get("/search", response_model=ApiResponse)
async def search_knowledge(
    q: str = Query(..., description="搜索关键词"),
    top_k: int = Query(5, ge=1, le=20),
):
    """语义搜索知识库"""
    try:
        from knowledge.vector_store import vector_store
        vector_store._ensure_initialized()
        results = await vector_store.similarity_search("user_knowledge", q, top_k=top_k)
        return ApiResponse(data={"query": q, "results": results, "count": len(results)})
    except Exception as e:
        logger.error(f"搜索失败: {e}")
        return ApiResponse(data={"query": q, "results": [], "count": 0, "error": str(e)})


# ── 后台处理 ───────────────────────────────────────────

def _process_document_async(doc_id: int, file_path: str, file_type: str):
    """在后台线程中执行文档处理管道"""
    import threading
    from models.session import get_session_local

    def _process():
        db = get_session_local()()
        try:
            doc = db.query(KnowledgeDocument).filter_by(id=doc_id).first()
            if not doc:
                return

            # 更新状态
            doc.processing_status = "extracting"
            db.commit()

            # 执行处理管道
            from knowledge.document_processor import document_processor
            result = document_processor.process(file_path, file_type)

            # 填充图片的 doc_id
            for img in result.get("images", []):
                img["doc_id"] = doc_id

            doc.processing_status = "chunking"
            doc.ocr_engine = result.get("ocr_engine", "none")
            doc.quality_score = result.get("quality_score", 0)
            doc.quality_notes = result.get("quality_notes", "")
            doc.has_latex = result.get("has_latex", False)
            doc.image_count = len(result.get("images", []))
            doc.table_count = len(result.get("tables", []))
            db.commit()

            # 分块 + 向量化
            from knowledge.chunker import knowledge_embedder
            text = result["text"]
            if text and len(text) > 50:
                chunk_count = knowledge_embedder.embed_document(
                    doc_id=doc_id,
                    text=text,
                    filename=doc.filename,
                    file_type=doc.file_type,
                    doc_category=doc.doc_category or "",
                    images=result.get("images", []),
                    tables=result.get("tables", []),
                    has_latex=result.get("has_latex", False),
                )
                doc.chunk_count = chunk_count
                doc.total_tokens = knowledge_embedder.estimate_tokens(text)
            else:
                doc.chunk_count = 0
                doc.processing_error = "文本提取结果为空"

            doc.processing_status = "ready" if doc.chunk_count > 0 else "error"
            db.commit()
            logger.info(f"文档 {doc_id} 处理完成: status={doc.processing_status}, chunks={doc.chunk_count}")

        except Exception as e:
            logger.error(f"文档 {doc_id} 处理失败: {e}")
            try:
                doc = db.query(KnowledgeDocument).filter_by(id=doc_id).first()
                if doc:
                    doc.processing_status = "error"
                    doc.processing_error = str(e)[:500]
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    t = threading.Thread(target=_process, daemon=True)
    t.start()
