"""
QueryDrawing Tool
查询当前图纸中的图元列表和状态，支持 COM 查询和视觉分析双模式
"""

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field


class QueryDrawingInput(BaseModel):
    """QueryDrawing 工具输入参数"""
    filter_label: str | None = Field(
        None,
        description="按设备标签过滤，如 'T1' 查询变压器 T1"
    )
    filter_layer: str | None = Field(
        None,
        description="按图层过滤，如 'ELEC-PROTECT'"
    )
    filter_type: str | None = Field(
        None,
        description="按图元类型过滤，如 'AcDbBlockReference'"
    )
    limit: int = Field(default=20, description="返回最多条数")
    mode: str = Field(
        default="auto",
        description="查询模式: 'com'=仅COM查询, 'visual'=仅视觉分析, 'auto'=COM+视觉（推荐，对非标准图纸自动启用视觉）"
    )


class QueryDrawingTool(BaseTool):
    """
    LangChain Tool：查询当前 AutoCAD 图纸的图元状态

    支持两种模式：
    - COM 查询：通过 AutoCAD COM API 读取图元属性（快速，适合标准图纸）
    - 视觉分析：截图 + 多模态 LLM 理解图纸（适合非标准/不规范图纸）

    默认 auto 模式会先 COM 查询，如果 COM 结果不理想（图元少或都是基础类型），
    自动追加视觉分析作为补充。
    """

    name: str = "query_drawing"
    description: str = (
        "查询 AutoCAD 当前图纸中的图元列表和内容。\n"
        "可按设备标签、图层或图元类型过滤。\n"
        "支持三种模式：\n"
        "- com: 仅通过 COM API 读取图元属性（快速）\n"
        "- visual: 仅通过截图+AI视觉分析理解图纸（适合非标准图纸）\n"
        "- auto: 自动模式，先 COM 查询，若结果不理想则自动追加视觉分析（推荐）\n"
        "对于已有图纸（非本系统绘制的），建议使用 visual 或 auto 模式，\n"
        "因为外部图纸可能不符合本系统的图层和图元规范。"
    )
    args_schema: type[BaseModel] = QueryDrawingInput

    def _run(
        self,
        filter_label: str | None = None,
        filter_layer: str | None = None,
        filter_type: str | None = None,
        limit: int = 20,
        mode: str = "auto",
    ) -> str:
        """执行查询"""
        com_result = ""
        visual_result = ""
        need_visual = False

        # ── 模式：com 或 auto ──────────────────────────────────────
        if mode in ("com", "auto"):
            try:
                com_result = self._com_query(filter_label, filter_layer, filter_type, limit)
            except ConnectionError:
                return "AutoCAD 未连接，无法查询图纸"
            except Exception as e:
                logger.error(f"COM query failed: {e}")
                com_result = f"[COM 查询异常: {e}]"

            # auto 模式下判断是否需要视觉分析
            if mode == "auto":
                need_visual = self._should_use_visual(com_result)

        # ── 模式：visual ──────────────────────────────────────────
        if mode == "visual" or (mode == "auto" and need_visual):
            try:
                from autocad.visual_reader import visual_reader as vr
                raw = vr.read()
                visual_result = vr.format_for_agent(raw, com_result if need_visual else "")
            except Exception as e:
                logger.error(f"Visual analysis failed: {e}")
                visual_result = f"\n\n[视觉分析异常: {e}]"

        # ── 组装结果 ──────────────────────────────────────────────
        if mode == "visual":
            return visual_result or "视觉分析未返回有效结果"

        if mode == "com":
            return com_result or "COM 查询未返回结果"

        # auto 模式
        if need_visual and visual_result:
            return (
                f"{com_result}\n\n"
                f"---\n"
                f"⚠️ COM 查询结果有限（图纸可能非本系统绘制），已自动启用视觉分析：\n\n"
                f"{visual_result}"
            )

        return com_result or "当前图纸无内容"

    def _com_query(
        self,
        filter_label: str | None,
        filter_layer: str | None,
        filter_type: str | None,
        limit: int,
    ) -> str:
        """COM API 查询"""
        from autocad.drawing_ops import drawing_ops

        entities = drawing_ops.get_all_entities()

        # 应用过滤
        if filter_layer:
            entities = [e for e in entities if e.get("layer", "").upper() == filter_layer.upper()]

        if filter_type:
            entities = [e for e in entities if filter_type.lower() in e.get("entity_type", "").lower()]

        # 按标签过滤（模糊匹配文字内容）
        if filter_label:
            filtered = []
            for e in entities:
                label = e.get("label", "") or e.get("text", "") or ""
                if filter_label.lower() in label.lower():
                    filtered.append(e)
            entities = filtered

        total = len(entities)
        entities = entities[:limit]

        if not entities:
            msg = "当前图纸为空"
            if filter_layer or filter_type or filter_label:
                msg = f"未找到符合条件的图元（layer={filter_layer}, type={filter_type}）"
            return msg

        lines = [f"当前图纸共 {total} 个图元（显示前 {len(entities)} 条）：\n"]
        for i, e in enumerate(entities, 1):
            x_str = f"{e['x']:.1f}" if e.get("x") is not None else "N/A"
            y_str = f"{e['y']:.1f}" if e.get("y") is not None else "N/A"
            label_info = f" 标注={e['label']}" if e.get("label") else ""
            lines.append(
                f"{i}. Handle={e['handle']} "
                f"类型={e['entity_type']} "
                f"图层={e['layer']} "
                f"位置=({x_str},{y_str}){label_info}"
            )

        return "\n".join(lines)

    def _should_use_visual(self, com_result: str) -> bool:
        """
        判断 COM 查询结果是否不够理想，需要启用视觉分析

        触发条件：
        - 图纸为空或图元很少（< 3 个）
        - 大部分是基础类型（AcDbLine/AcDbPolyline/AcDbText），不是标准块
        - 图层不规范（没有 ELEC- 前缀图层）
        """
        if not com_result or "为空" in com_result or "未找到" in com_result:
            logger.info("QueryDrawing: COM result empty, enabling visual analysis")
            return True

        # 统计图元数
        import re
        match = re.search(r'共\s*(\d+)\s*个图元', com_result)
        entity_count = int(match.group(1)) if match else 0

        # 统计标准图层的图元
        standard_layers = sum(
            1 for layer in ["ELEC-", "电气", "ELECTRICAL", "POWER"]
            if layer.upper() in com_result.upper()
        )

        # 统计块引用（INSERT/BlockReference）
        block_count = len(re.findall(r'AcDbBlockReference|INSERT', com_result, re.IGNORECASE))

        if entity_count < 3:
            logger.info(f"QueryDrawing: only {entity_count} entities, enabling visual")
            return True

        if block_count == 0 and entity_count > 0:
            logger.info(f"QueryDrawing: no blocks found among {entity_count} entities, enabling visual")
            return True

        if standard_layers == 0 and entity_count > 0:
            logger.info("QueryDrawing: no standard layers, enabling visual")
            return True

        logger.info(f"QueryDrawing: COM result looks good ({entity_count} entities, {block_count} blocks), skipping visual")
        return False

    async def _arun(self, **kwargs) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))
