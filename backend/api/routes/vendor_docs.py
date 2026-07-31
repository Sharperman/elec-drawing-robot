"""
厂家资料解析路由 — P1-03
POST /api/vendor-docs/parse  - 上传 PDF/图片，提取设备参数
POST /api/vendor-docs/apply  - 将解析结果应用到当前图纸
"""
import base64
import json

from api.schemas import ApiResponse
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from loguru import logger

router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_TYPES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/bmp", "image/tiff", "image/webp",
}


@router.post("/parse", response_model=ApiResponse)
async def parse_vendor_doc(
    file: UploadFile = File(...),
    session_id: str = Form(""),
) -> ApiResponse:
    """
    解析厂家设备资料（PDF 或图片），提取设备参数。

    流程：
    1. 接收文件，验证类型和大小
    2. PDF → 提取文本；图片 → base64 传入 LLM
    3. LLM 提取结构化设备参数
    4. 返回设备列表和材料表
    """
    # 验证
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {file.content_type}")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，最大 {MAX_FILE_SIZE // 1024 // 1024}MB")

    logger.info(f"Parsing vendor doc: {file.filename} ({len(content)} bytes)")

    try:
        is_pdf = file.content_type == "application/pdf" or file.filename.lower().endswith('.pdf')
        text_content = ""

        if is_pdf:
            # PDF 文本提取
            text_content = _extract_pdf_text(content, file.filename)
        else:
            # 图片：传入 LLM 作为视觉输入
            img_b64 = base64.b64encode(content).decode("utf-8")
            mime = file.content_type or "image/png"
            text_content = await _extract_image_text(img_b64, mime)

        if not text_content or len(text_content.strip()) < 10:
            return ApiResponse(
                message="未能从文件中提取到有效文本，请确认文件包含文字信息",
                data={"equipment": [], "material_list": []},
            )

        # LLM 提取结构化设备参数
        result = await _extract_equipment_params(text_content)

        return ApiResponse(
            message=f"解析完成，识别到 {len(result.get('equipment', []))} 台设备",
            data=result,
        )

    except Exception as e:
        logger.error(f"Failed to parse vendor doc: {e}")
        raise HTTPException(status_code=500, detail=f"解析失败: {str(e)}")


@router.post("/apply", response_model=ApiResponse)
async def apply_vendor_result(
    data: dict,
) -> ApiResponse:
    """
    将解析结果应用到当前 AutoCAD 图纸。

    Body:
    {
        "equipment": [...],
        "material_list": [...]
    }
    """
    equipment = data.get("equipment", [])
    material_list = data.get("material_list", [])

    if not equipment:
        return ApiResponse(message="没有可应用的设备", data={})

    try:
        from agent.draw_agent import get_agent
        from autocad.connection import autocad_connection

        acad = autocad_connection
        if not acad.is_connected:
            return ApiResponse(
                code=1002,
                message="AutoCAD 未连接，无法应用设备",
            )

        agent = get_agent("vendor-docs")

        # 构建插入指令
        eq_desc = "\n".join(
            f"- {eq.get('name', '设备')}: {eq.get('model', '')} "
            f"(参数: {json.dumps(eq.get('params', {}), ensure_ascii=False)})"
            for eq in equipment[:10]
        )

        prompt = f"""请在 AutoCAD 中插入以下厂家设备：

{eq_desc}

请按设备清单依次插入对应的电气符号，并标注型号和关键参数。"""

        full_response = ""
        async for event in agent.chat_stream(
            user_input=prompt,
            standards_context="",
            learned_rules=[],
            acad_connected=True,
            drawing_name="厂家设备导入",
            mode="draw",
        ):
            if event.get("type") == "text":
                full_response += event.get("content", "")

        return ApiResponse(
            message=f"已应用 {len(equipment)} 台设备到图纸",
            data={"applied_count": len(equipment), "response": full_response[:500]},
        )

    except Exception as e:
        logger.error(f"Failed to apply vendor result: {e}")
        raise HTTPException(status_code=500, detail=f"应用失败: {str(e)}")


# ─── 内部函数 ──────────────────────────────────────────────────

def _extract_pdf_text(content: bytes, filename: str) -> str:
    """从 PDF 提取文本"""
    try:
        import io

        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        texts = []
        for page in reader.pages[:10]:  # 最多10页
            t = page.extract_text()
            if t:
                texts.append(t)
        return "\n".join(texts)
    except ImportError:
        logger.warning("PyPDF2 not installed, cannot extract PDF text")
        return ""
    except Exception as e:
        logger.warning(f"PDF extraction failed: {e}")
        return ""


async def _extract_image_text(img_b64: str, mime: str) -> str:
    """通过 LLM 视觉能力提取图片中的文字（使用多模态 LLM）"""
    try:
        from agent.llm_factory import create_vision_llm

        llm = create_vision_llm(
            temperature=0,
            max_tokens=2000,
        )

        from langchain_core.messages import HumanMessage
        msg = HumanMessage(
            content=[
                {"type": "text", "text": "请提取这张电气设备资料图片中的所有文字信息，包括设备型号、技术参数、外形尺寸等。直接输出提取到的文字，不要添加额外说明。"},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{img_b64}"}},
            ]
        )
        resp = await llm.ainvoke([msg])
        return resp.content if hasattr(resp, 'content') else str(resp)
    except Exception as e:
        logger.warning(f"Image text extraction failed: {e}")
        return ""


async def _extract_equipment_params(text: str) -> dict:
    """通过 LLM 从文本中提取结构化设备参数（使用主力 LLM）"""
    try:
        from agent.llm_factory import create_primary_llm

        llm = create_primary_llm(
            temperature=0.1,
            max_tokens=2000,
        )

        prompt = f"""从以下厂家设备资料中提取所有电气设备的结构化参数。请生成如下JSON（仅输出JSON）：

{{
  "equipment": [
    {{
      "name": "设备名称（如：真空断路器）",
      "model": "型号（如：ZN63A-12）",
      "quantity": 1,
      "params": {{
        "rated_voltage": "额定电压",
        "rated_current": "额定电流",
        "其他参数": "值"
      }},
      "dimensions": "外形尺寸（如有）"
    }}
  ],
  "material_list": [
    {{
      "name": "材料名称",
      "spec": "规格",
      "quantity": 1,
      "unit": "台/套/米"
    }}
  ]
}}

原始资料文本：
{text[:4000]}

规则：
- equipment 数组列出所有识别到的电气设备
- params 中提取所有技术参数
- material_list 为材料清单
- 如果某项信息缺失，留空字符串
- 不要编造不存在的信息"""

        from langchain_core.messages import HumanMessage
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        content = resp.content if hasattr(resp, 'content') else str(resp)

        # 提取 JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            return json.loads(json_match.group())

        return {"equipment": [], "material_list": []}

    except Exception as e:
        logger.warning(f"Equipment param extraction failed: {e}")
        return {"equipment": [], "material_list": []}
