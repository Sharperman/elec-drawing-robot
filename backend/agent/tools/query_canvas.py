"""
QueryCanvas Tool
查询画布状态记忆（CanvasState），让 LLM 了解当前图纸上有什么
"""

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class QueryCanvasInput(BaseModel):
    """QueryCanvas 工具输入参数"""
    query_type: str = Field(
        default="summary",
        description=(
            "查询类型：\n"
            "- summary: 画布全局摘要（设备清单+连线+空间信息），推荐每次绘图前调用\n"
            "- devices: 按条件列出设备（使用 filter_label/filter_type/filter_layer 过滤）\n"
            "- connections: 列出连线关系\n"
            "- find_space: 查找空白区域，用于放置新设备\n"
            "- device_detail: 查询特定设备的详细信息（需指定 filter_label）"
        ),
    )
    filter_label: str | None = Field(
        None,
        description="按设备编号过滤，如 'T1'、'QF1'。支持模糊匹配。用于 query_type='devices' 或 'device_detail'",
    )
    filter_type: str | None = Field(
        None,
        description="按设备类型过滤，如 'TR_2W'、'CB_3P'。用于 query_type='devices'",
    )
    filter_layer: str | None = Field(
        None,
        description="按图层过滤，如 'ELEC-POWER'。用于 query_type='devices'",
    )


class QueryCanvasTool(BaseTool):
    """
    LangChain Tool：查询画布状态记忆

    LLM 通过此工具获取当前画布上的所有设备、连线、标注，
    以及空间信息和布局建议。

    关键原则：LLM 不应该"记住"画布状态，而应该"需要时查询"。
    画布状态由系统自动维护（每次 insert/draw/modify 后更新）。
    """

    name: str = "query_canvas"
    description: str = (
        "查询当前 AutoCAD 画布的状态记忆（本系统自动追踪的设备/连线/标注）。\n\n"
        "## 何时使用\n"
        "- 每次准备绘图前：先用 query_type='summary' 了解画布全貌\n"
        "- 需要知道前面画了什么设备、放在哪了：query_type='devices'\n"
        "- 需要规划新设备放哪不重叠：query_type='find_space'\n"
        "- 需要了解设备间的连接关系：query_type='connections'\n\n"
        "## 与 query_drawing 的区别\n"
        "- query_drawing: 查询 AutoCAD 中的真实图元（每次都走 COM/视觉）\n"
        "- query_canvas: 查询本系统的画布状态缓存（快速、结构化、含布局建议）\n\n"
        "## 参数说明\n"
        "- query_type='summary': 返回完整画布摘要（设备列表+连线+空间）\n"
        "- query_type='devices': 支持 filter_label/filter_type/filter_layer 过滤\n"
        "- query_type='find_space': 查找空白区域，返回建议坐标\n"
        "- query_type='device_detail': 查询指定 label 的设备详情\n"
        "- query_type='connections': 返回所有连线关系"
    )
    args_schema: type[BaseModel] = QueryCanvasInput

    # ── canvas_state 由 DrawAgent 在构建时注入 ──
    # 使用 ClassVar 避免被 Pydantic 序列化
    canvas_state: object = Field(default=None, exclude=True)

    def _run(
        self,
        query_type: str = "summary",
        filter_label: str | None = None,
        filter_type: str | None = None,
        filter_layer: str | None = None,
    ) -> str:
        """执行画布状态查询"""
        if self.canvas_state is None:
            return "⚠️ 画布状态追踪未初始化，请先连接 AutoCAD 并开始绘图。"

        cs = self.canvas_state

        if query_type == "summary":
            return cs.get_summary()

        elif query_type == "devices":
            devices = cs.find_devices(
                label=filter_label,
                symbol_id=filter_type,
                layer=filter_layer,
            )
            if not devices:
                filters = []
                if filter_label:
                    filters.append(f"编号={filter_label}")
                if filter_type:
                    filters.append(f"类型={filter_type}")
                if filter_layer:
                    filters.append(f"图层={filter_layer}")
                return f"未找到匹配的设备（筛选条件：{', '.join(filters)}）"

            lines = [f"# 设备查询结果（{len(devices)} 个）\n"]
            for d in devices:
                lbl = f"[{d.label}] " if d.label else ""
                lines.append(
                    f"- {d.symbol_id} {lbl}@ ({d.x:.0f}, {d.y:.0f}) "
                    f"图层={d.layer} Handle={d.handle}"
                )
            return "\n".join(lines)

        elif query_type == "connections":
            if not cs.connections:
                return "当前无连线关系。"

            lines = [f"# 连线关系（{len(cs.connections)} 条）\n"]
            for c in cs.connections:
                fl = c.from_label or c.from_handle
                tl = c.to_label or c.to_handle
                lines.append(f"- {fl} → {tl} [{c.line_type}] 图层={c.layer}")
            return "\n".join(lines)

        elif query_type == "find_space":
            region = cs.find_empty_region()
            lines = [
                "# 空白区域查找",
                f"策略: {region['strategy']}",
                f"建议坐标: ({region['x']:.0f}, {region['y']:.0f})",
            ]
            if cs.devices:
                lines.append(f"\n当前画布范围: X [{cs._min_x:.0f} ~ {cs._max_x:.0f}] Y [{cs._min_y:.0f} ~ {cs._max_y:.0f}]")
                lines.append(f"已有 {cs.device_count} 个设备，{cs.connection_count} 条连线")
            return "\n".join(lines)

        elif query_type == "device_detail":
            if not filter_label:
                return "错误：device_detail 模式需要指定 filter_label 参数"

            devices = cs.find_devices(label=filter_label)
            if not devices:
                return f"未找到编号包含 '{filter_label}' 的设备"

            lines = [f"# 设备详情: {filter_label}\n"]
            for d in devices:
                lines.append(f"## {d.symbol_id} [{d.label or '未编号'}]")
                lines.append(f"- Handle: {d.handle}")
                lines.append(f"- 位置: ({d.x:.0f}, {d.y:.0f})")
                lines.append(f"- 图层: {d.layer}")
                lines.append(f"- 旋转: {d.rotation:.2f} rad | 缩放: {d.scale:.2f}")

                # 相关连线
                conns = cs.get_connections_for(d.handle)
                if conns:
                    lines.append(f"- 连线数: {len(conns)}")
                    for c in conns:
                        other = c.to_label or c.to_handle
                        if c.to_handle == d.handle:
                            other = c.from_label or c.from_handle
                        lines.append(f"  {'←' if c.to_handle == d.handle else '→'} {other} [{c.line_type}]")

                # 相关标注
                anns = [a for a in cs.annotations if a.target_handle == d.handle]
                if anns:
                    lines.append("- 标注:")
                    for a in anns:
                        lines.append(f"  \"{a.text}\" @ ({a.x:.0f},{a.y:.0f})")

            return "\n".join(lines)

        else:
            return f"未知查询类型: {query_type}，支持: summary | devices | connections | find_space | device_detail"

    async def _arun(self, **kwargs) -> str:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))
