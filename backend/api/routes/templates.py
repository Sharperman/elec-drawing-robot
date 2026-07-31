"""
图纸模板库路由
GET  /api/templates         - 列出所有模板（可按分类筛选）
GET  /api/templates/{id}    - 获取单个模板详情
POST /api/templates/{id}/apply - 应用模板到当前 AutoCAD 图纸
"""
import json
from pathlib import Path

from api.schemas import ApiResponse
from fastapi import APIRouter, HTTPException

router = APIRouter()

# 模板数据路径
TEMPLATES_FILE = Path(__file__).parent.parent.parent / "knowledge" / "data" / "templates" / "templates.json"


def _load_templates() -> list[dict]:
    """加载所有模板"""
    if not TEMPLATES_FILE.exists():
        return []
    with open(TEMPLATES_FILE, encoding="utf-8") as f:
        return json.load(f)


@router.get("", response_model=ApiResponse)
async def list_templates(category: str = "") -> ApiResponse:
    """列出所有图纸模板，可按分类筛选"""
    templates = _load_templates()
    if category:
        templates = [t for t in templates if t.get("category") == category]

    # 只返回摘要
    summaries = [
        {
            "id": t["id"],
            "name": t["name"],
            "category": t["category"],
            "description": t["description"],
            "voltage_level": t.get("voltage_level", ""),
            "element_count": len(t.get("elements", [])),
        }
        for t in templates
    ]

    # 同时返回所有分类
    categories = list(set(t["category"] for t in templates))
    return ApiResponse(
        data={"templates": summaries, "categories": categories, "total": len(summaries)},
    )


@router.get("/{template_id}", response_model=ApiResponse)
async def get_template(template_id: str) -> ApiResponse:
    """获取单个模板的完整详情"""
    templates = _load_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return ApiResponse(data=template)


@router.post("/{template_id}/apply", response_model=ApiResponse)
async def apply_template(template_id: str) -> ApiResponse:
    """
    应用模板到当前 AutoCAD 图纸

    步骤：
    1. 加载模板数据
    2. 创建模板中定义的图层
    3. 按模板元素描述，调用 Agent 在 AutoCAD 中绘制
    """
    templates = _load_templates()
    template = next((t for t in templates if t["id"] == template_id), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        from autocad.connection import autocad_connection

        acad = autocad_connection
        if not acad.is_connected:
            return ApiResponse(
                code=1002,
                message="AutoCAD 未连接，无法应用模板",
            )

        # 1. 创建图层
        for layer in template.get("layer_config", []):
            try:
                acad.ensure_layer(
                    name=layer["name"],
                    color=layer.get("color", "white"),
                    linetype=layer.get("linetype", "Continuous"),
                )
            except Exception:
                pass  # 图层可能已存在

        # 2. 遍历模板元素，调用 Agent 插入
        from agent.draw_agent import get_agent
        agent = get_agent(f"tpl-{template_id}")

        element_list = "\n".join(
            f"- {el['type']}: {el['name']}" + (
                f" (参数: {el['params']})" if el.get("params") else ""
            )
            for el in template.get("elements", [])
        )

        prompt = f"""请按以下模板创建图纸：
模板名称：{template['name']}
分类：{template.get('category', '')}
电压等级：{template.get('voltage_level', '')}

需要绘制的元件：
{element_list}

请依次插入所有元件，使用模板中指定的图层。"""

        full_response = ""
        async for event in agent.chat_stream(
            user_input=prompt,
            standards_context="",
            learned_rules=[],
            acad_connected=True,
            drawing_name=template["name"],
            mode="draw",
        ):
            if event.get("type") == "text":
                full_response += event.get("content", "")

        return ApiResponse(
            message=f"模板「{template['name']}」已应用",
            data={
                "template_id": template_id,
                "template_name": template["name"],
                "elements_count": len(template.get("elements", [])),
                "response": full_response[:500],
            },
        )

    except Exception as e:
        from loguru import logger
        logger.error(f"Failed to apply template: {e}")
        raise HTTPException(status_code=500, detail=f"应用模板失败: {str(e)}")
