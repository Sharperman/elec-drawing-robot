"""
知识文档处理器
负责多格式文档的文本提取、OCR 和质量检查。
新增: 图片提取保存 + 表格结构化提取 + LaTeX 公式检测

流程: L1(原生提取) → L2(PaddleOCR) → 质量判断(LLM) → L3(Vision LLM 重扫,按需)
"""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import re

from loguru import logger

# ── PaddleOCR 延迟加载 ──────────────────────────────

def _get_paddle_ocr():
    """延迟加载 PaddleOCR（避免冷启动加载到所有进程）"""
    try:
        from paddleocr import PaddleOCR
        return PaddleOCR(lang='ch', use_angle_cls=True, show_log=False)
    except ImportError:
        logger.warning("PaddleOCR not installed, falling back to pytesseract")
    except Exception as e:
        logger.warning(f"PaddleOCR init failed: {e}")
    return None


def _get_tesseract():
    """Tesseract fallback"""
    try:
        from PIL import Image
        import pytesseract
        return True
    except ImportError:
        logger.warning("pytesseract not installed")
    return False


# ── L1: 原生文本提取 ─────────────────────────────────

def extract_text_native(file_path: str, file_type: str) -> tuple[str, int]:
    """
    从数字文档中提取纯文本。
    返回 (text, char_count)
    """
    text = ""
    try:
        if file_type == "pdf":
            text = _extract_pdf_text(file_path)
        elif file_type == "docx":
            text = _extract_docx_text(file_path)
        elif file_type == "pptx":
            text = _extract_pptx_text(file_path)
        elif file_type == "txt":
            text = Path(file_path).read_text(encoding="utf-8", errors="replace")
        else:
            return "", 0
    except Exception as e:
        logger.warning(f"原生提取失败 ({file_type}): {e}")
        return "", 0

    # 清理
    text = re.sub(r'\n{4,}', '\n\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    return text.strip(), len(text)


def _extract_pdf_text(file_path: str) -> str:
    """PyMuPDF 提取 PDF 文本"""
    import fitz
    doc = fitz.open(file_path)
    pages = []
    for page in doc:
        t = page.get_text("text")
        if t.strip():
            pages.append(t.strip())
    doc.close()
    return "\n\n--- PAGE BREAK ---\n\n".join(pages)


def _extract_docx_text(file_path: str) -> str:
    """python-docx 提取 Word 文本"""
    from docx import Document
    doc = Document(file_path)
    paras = []
    for p in doc.paragraphs:
        if p.text.strip():
            paras.append(p.text.strip())
    return "\n\n".join(paras)


def _extract_pptx_text(file_path: str) -> str:
    """python-pptx 提取 PPT 文本"""
    from pptx import Presentation
    prs = Presentation(file_path)
    slides = []
    for i, slide in enumerate(prs.slides, 1):
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    if para.text.strip():
                        texts.append(para.text.strip())
        if texts:
            slides.append(f"## Slide {i}\n" + "\n".join(texts))
    return "\n\n--- SLIDE BREAK ---\n\n".join(slides)


# ── L2: OCR 引擎 ────────────────────────────────────

def extract_text_ocr(file_path: str, file_type: str) -> tuple[str, int, str]:
    """
    OCR 文本提取。优先 PaddleOCR → Tesseract fallback。
    返回 (text, char_count, engine_name)
    """
    engine_name = "none"
    text = ""

    # 对于没法原生提取的格式 (图片, 扫描PDF)，提取页面图像
    images = _get_page_images(file_path, file_type)
    if not images:
        return "", 0, "none"

    # 尝试 PaddleOCR
    ocr = _get_paddle_ocr()
    if ocr is not None:
        try:
            parts = []
            for img_bytes in images:
                from PIL import Image
                img = Image.open(io.BytesIO(img_bytes))
                result = ocr.ocr(img, cls=True)
                if result and result[0]:
                    page_text = "\n".join(
                        line[1][0] for line in result[0] if line and len(line) > 1
                    )
                    if page_text.strip():
                        parts.append(page_text)
            text = "\n\n--- PAGE BREAK ---\n\n".join(parts)
            if text.strip():
                engine_name = "paddle"
                return text.strip(), len(text), engine_name
        except Exception as e:
            logger.warning(f"PaddleOCR failed: {e}")

    # Fallback: Tesseract
    if _get_tesseract():
        try:
            from PIL import Image
            import pytesseract
            parts = []
            for img_bytes in images:
                img = Image.open(io.BytesIO(img_bytes))
                page_text = pytesseract.image_to_string(img, lang="chi_sim+eng")
                if page_text.strip():
                    parts.append(page_text.strip())
            text = "\n\n--- PAGE BREAK ---\n\n".join(parts)
            if text.strip():
                engine_name = "tesseract"
                return text.strip(), len(text), engine_name
        except Exception as e:
            logger.warning(f"Tesseract failed: {e}")

    return "", 0, engine_name


def _get_page_images(file_path: str, file_type: str) -> list[bytes]:
    """从文档中提取页面图像 (bytes)"""
    images = []
    try:
        if file_type == "pdf":
            import fitz
            doc = fitz.open(file_path)
            for page in doc:
                pix = page.get_pixmap(dpi=200)
                images.append(pix.tobytes("png"))
            doc.close()
        elif file_type in ("jpg", "jpeg", "png", "bmp", "tiff", "tif", "image"):
            with open(file_path, "rb") as f:
                images.append(f.read())
    except Exception as e:
        logger.error(f"提取页面图像失败: {e}")
    return images


# ── 质量判断 ─────────────────────────────────────────

# 质量检查 prompt（简短版，快速判断）
QUALITY_CHECK_PROMPT = """你是文档质量专家。评估以下OCR提取结果的质量。

原文片段（前500字）:
{original_sample}

评价标准:
- 中文识别准确率
- 表格/公式是否被识别
- 段落结构是否保持
- 专业术语是否完整

请只返回JSON:
{{"score": 0.0-1.0, "passed": true/false, "issues": ["问题1", "问题2"], "needs_l3": true/false, "notes": "一句话总结"}}
"""


def check_quality(text: str, file_type: str) -> dict:
    """
    LLM 质量判断。如果 L1 效果好，跳过 L2/L3。
    返回 {"score": float, "passed": bool, "needs_l3": bool, "issues": list, "notes": str}
    """
    # 对纯文本文件，不需要质量检查
    if file_type == "txt":
        return {"score": 1.0, "passed": True, "needs_l3": False, "issues": [], "notes": "纯文本，无需检查"}

    char_count = len(text)

    # 如果文本太少，直接标记需要 OCR
    if char_count < 100:
        return {
            "score": 0.0, "passed": False, "needs_l3": True,
            "issues": [f"文本量不足 ({char_count} 字符)"],
            "notes": "L1 提取文本过少，需进行 OCR",
        }

    # 如果文本充足，用 LLM 快速判断
    try:
        from agent.llm_factory import create_primary_llm
        from langchain_core.messages import HumanMessage
        from models.session import get_session_local

        db = get_session_local()()
        llm = create_primary_llm(db=db)
        db.close()

        sample = text[:800]
        prompt = QUALITY_CHECK_PROMPT.format(original_sample=sample)
        resp = llm.invoke([HumanMessage(content=prompt)])
        content = resp.content if hasattr(resp, "content") else str(resp)

        # 解析 JSON
        import re as _re
        m = _re.search(r'\{[\s\S]*\}', content)
        if m:
            result = json.loads(m.group())
            result["char_count"] = char_count
            return result

    except Exception as e:
        logger.warning(f"质量检查 LLM 调用失败: {e}")

    # 兜底：基于字符数判断
    return {
        "score": min(char_count / 5000, 0.9), "passed": char_count > 500,
        "needs_l3": char_count < 2000, "issues": [],
        "notes": f"基于字符数 ({char_count}) 自动判断",
    }


# ── L3: Vision LLM 重扫 ─────────────────────────────

def extract_text_vision_llm(file_path: str, file_type: str, max_pages: int = 20) -> tuple[str, int]:
    """
    使用 Vision LLM 对文档页面进行重扫（仅用于质量不达标的文档）。
    返回 (text, char_count)
    """
    images = _get_page_images(file_path, file_type)
    if not images:
        return "", 0

    pages = images[:max_pages]
    parts = []
    try:
        from agent.llm_factory import create_vision_llm
        from langchain_core.messages import HumanMessage
        from models.session import get_session_local

        db = get_session_local()()
        llm = create_vision_llm(db=db)
        db.close()

        for i, img_bytes in enumerate(pages):
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            msg = HumanMessage(content=[
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
                },
                {
                    "type": "text",
                    "text": "请精确识别并转写此页面上的所有文字内容（中文和英文），包括表格、标题和正文。保持原始段落结构。只输出纯文本。",
                },
            ])
            resp = llm.invoke([msg])
            content = resp.content if hasattr(resp, "content") else str(resp)
            if content.strip():
                parts.append(content.strip())
            logger.info(f"L3 OCR: page {i+1}/{len(pages)} ok")

    except Exception as e:
        logger.error(f"L3 Vision LLM 失败: {e}")
        return "", 0

    text = "\n\n--- PAGE BREAK ---\n\n".join(parts)
    return text.strip(), len(text)


# ── 图片提取 ──────────────────────────────────────

def extract_pdf_images(file_path: str, output_dir: str, doc_id: int) -> list[dict]:
    """
    从 PDF 提取嵌入式图片，保存到 output_dir。
    返回 [{"path": "...", "page": 1, "width": 800, "height": 600, "caption": ""}, ...]
    """
    results = []
    try:
        import fitz
        os.makedirs(output_dir, exist_ok=True)
        doc = fitz.open(file_path)
        for page_num, page in enumerate(doc, 1):
            image_list = page.get_images(full=True)
            for img_idx, img in enumerate(image_list):
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                ext = base_image["ext"]
                w, h = base_image.get("width", 0), base_image.get("height", 0)

                # 跳过太小的图片（可能是图标/装饰）
                if w < 50 or h < 50:
                    continue

                img_name = f"doc{doc_id}_p{page_num}_img{img_idx}.{ext}"
                img_path = os.path.join(output_dir, img_name)
                with open(img_path, "wb") as f:
                    f.write(img_bytes)

                results.append({
                    "path": img_path,
                    "page": page_num,
                    "width": w,
                    "height": h,
                    "caption": "",
                })
        doc.close()
        logger.info(f"提取 PDF 图片: {len(results)} 张")
    except Exception as e:
        logger.warning(f"PDF 图片提取失败: {e}")
    return results


# ── 表格提取 ──────────────────────────────────────

def extract_pdf_tables(file_path: str) -> list[str]:
    """
    使用 PyMuPDF 的表格检测提取 PDF 表格为 Markdown 格式。
    返回 ["| A | B |\n| 1 | 2 |", ...]
    """
    tables = []
    try:
        import fitz
        doc = fitz.open(file_path)
        for page in doc:
            tabs = page.find_tables()
            if tabs and tabs.tables:
                for tab in tabs.tables:
                    md = _table_to_markdown(tab.extract())
                    if md:
                        tables.append(md)
        doc.close()
    except Exception as e:
        logger.warning(f"PDF 表格提取失败: {e}")
    return tables


def extract_docx_tables(file_path: str) -> list[str]:
    """从 Word 文档提取表格为 Markdown 格式"""
    tables = []
    try:
        from docx import Document
        doc = Document(file_path)
        for table in doc.tables:
            rows = []
            for row in table.rows:
                cells = [cell.text.replace("\n", " ").strip() for cell in row.cells]
                rows.append(cells)
            if rows:
                md = _table_to_markdown(rows)
                if md:
                    tables.append(md)
    except Exception as e:
        logger.warning(f"DOCX 表格提取失败: {e}")
    return tables


def _table_to_markdown(rows: list[list[str]]) -> str:
    """将二维列表转为 Markdown 表格"""
    if not rows or not rows[0]:
        return ""
    max_cols = max(len(r) for r in rows)
    # 补全
    for r in rows:
        while len(r) < max_cols:
            r.append("")

    lines = []
    # header
    lines.append("| " + " | ".join(str(c) for c in rows[0]) + " |")
    # separator
    lines.append("| " + " | ".join("---" for _ in range(max_cols)) + " |")
    # data rows
    for row in rows[1:]:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")

    return "\n".join(lines)


# ── LaTeX 公式检测 ────────────────────────────────

# 常见 LaTeX 公式模式
_LATEX_PATTERNS = [
    r'\$[^$]+\$',                        # 行内公式 $...$
    r'\$\$[\s\S]+?\$\$',                 # 块公式 $$...$$
    r'\\\[[\s\S]+?\\\]',                 # 显示公式 \[...\]
    r'\\\([\s\S]+?\\\)',                 # 行内公式 \(...\)
    r'\\begin\{equation\}[\s\S]+?\\end\{equation\}',
    r'\\begin\{align\}[\s\S]+?\\end\{align\}',
    r'\\begin\{gather\}[\s\S]+?\\end\{gather\}',
]

def detect_latex(text: str) -> dict:
    """
    检测文本中的 LaTeX 公式。
    返回 {"has_latex": bool, "count": int, "formulas": [str, ...]}
    """
    formulas = []
    for pattern in _LATEX_PATTERNS:
        matches = re.findall(pattern, text, re.DOTALL)
        for m in matches:
            stripped = m.strip()
            if len(stripped) > 4:  # 忽略 $ $ 空公式
                formulas.append(stripped)

    return {
        "has_latex": len(formulas) > 0,
        "count": len(formulas),
        "formulas": formulas[:20],  # 最多保留20个样本
    }


def generate_image_caption(image_path: str) -> str:
    """
    使用 LLM 为图片生成简短标注（用于向量检索）。
    只在图片足够大（>100KB）时才调用，小图片跳过。
    """
    try:
        if os.path.getsize(image_path) < 50 * 1024:
            return ""
    except Exception:
        return ""

    try:
        with open(image_path, "rb") as f:
            img_bytes = f.read()
        b64 = base64.b64encode(img_bytes).decode("utf-8")

        from agent.llm_factory import create_vision_llm
        from langchain_core.messages import HumanMessage
        from models.session import get_session_local

        db = get_session_local()()
        llm = create_vision_llm(db=db)
        db.close()

        msg = HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "low"}},
            {"type": "text", "text": "用一句话（不超过30个汉字）描述这张图片的内容。如果是表格，说明表头列名。如果是电气图纸，说明图纸类型。只输出描述文本。"},
        ])
        resp = llm.invoke([msg])
        caption = resp.content.strip() if hasattr(resp, "content") else str(resp).strip()
        return caption[:100]
    except Exception as e:
        logger.warning(f"图片标注生成失败: {e}")
        return ""


# ── 全流程处理器 ──────────────────────────────────

class DocumentProcessor:
    """
    文档处理管道: L1 → 质量检查 → (L2 if needed) → 质量检查 → (L3 if needed)
    """

    def process(self, file_path: str, file_type: str) -> dict:
        """
        处理单个文档，返回结果字典:
        {
            "text": str,
            "char_count": int,
            "ocr_engine": "native"|"paddle"|"tesseract"|"l3_vision",
            "quality_score": float,
            "quality_notes": str,
            "l1_result": {...},
            "l2_result": {...},
            "l3_result": {...},
        }
        """
        result = {
            "text": "", "char_count": 0, "ocr_engine": "none",
            "quality_score": 0.0, "quality_notes": "",
            "l1_result": {}, "l2_result": {}, "l3_result": {},
            "images": [], "tables": [], "has_latex": False, "latex_count": 0,
        }

        # ── 图片提取（并行，不依赖 OCR）──
        if file_type in ("pdf", "jpg", "jpeg", "png"):
            img_dir = os.path.join("data", "knowledge_images", str(hashlib.md5(file_path.encode()).hexdigest()[:8]))
            result["images"] = extract_pdf_images(file_path, img_dir, 0)  # doc_id 在外层填充

        # ── 表格提取 ──
        if file_type == "pdf":
            result["tables"] = extract_pdf_tables(file_path)
        elif file_type == "docx":
            result["tables"] = extract_docx_tables(file_path)

        # ── L1: 原生提取 ──
        text, count = extract_text_native(file_path, file_type)
        result["l1_result"] = {"text": text, "char_count": count}

        # 质量检查
        if count > 0:
            quality = check_quality(text, file_type)
        else:
            quality = {"score": 0, "passed": False, "needs_l3": True, "issues": ["无文本"],
                       "notes": "L1 无输出"}

        result["quality_score"] = quality.get("score", 0)
        result["quality_notes"] = quality.get("notes", "")

        if quality.get("passed"):
            result["text"] = text
            result["char_count"] = count
            result["ocr_engine"] = "native"
            return result

        # ── L2: OCR ──
        logger.info(f"L1 质量不达标 ({count} chars, score={quality.get('score')}), 执行 L2 OCR...")
        ocr_text, ocr_count, engine = extract_text_ocr(file_path, file_type)
        result["l2_result"] = {"text": ocr_text, "char_count": ocr_count, "engine": engine}

        if ocr_count > 0:
            quality2 = check_quality(ocr_text, file_type)
            result["quality_score"] = max(result["quality_score"], quality2.get("score", 0))
            result["quality_notes"] = quality2.get("notes", result["quality_notes"])
            if quality2.get("passed") and not quality2.get("needs_l3"):
                result["text"] = ocr_text
                result["char_count"] = ocr_count
                result["ocr_engine"] = engine
                return result

        # ── L3: Vision LLM ──
        logger.info("L2 仍需改进 (needs_l3=True), 执行 L3 Vision LLM...")
        l3_text, l3_count = extract_text_vision_llm(file_path, file_type)
        result["l3_result"] = {"text": l3_text, "char_count": l3_count}

        if l3_count > 0:
            result["text"] = l3_text
            result["char_count"] = l3_count
            result["ocr_engine"] = "l3_vision"
            result["quality_score"] = 0.85  # L3 默认较高
            result["quality_notes"] = "Vision LLM 重扫"
        else:
            # 全部失败，回退到最好的结果
            if ocr_count > count:
                result["text"] = ocr_text
                result["char_count"] = ocr_count
                result["ocr_engine"] = engine
            elif count > 0:
                result["text"] = text
                result["char_count"] = count
                result["ocr_engine"] = "native"

        # LaTeX 公式检测
        latex_info = detect_latex(result["text"])
        result["has_latex"] = latex_info["has_latex"]
        result["latex_count"] = latex_info["count"]

        return result


# 全局单例
document_processor = DocumentProcessor()
