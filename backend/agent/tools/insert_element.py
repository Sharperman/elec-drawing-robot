"""
InsertElement Tool
根据 symbol_id 和位置将电气图元插入到 AutoCAD
"""

from langchain_core.tools import BaseTool
from loguru import logger
from pydantic import BaseModel, Field


class InsertElementInput(BaseModel):
    """InsertElement 工具输入参数"""
    symbol_id: str = Field(..., description="图元符号 ID，如 CB_3P、TR_2W、GND")
    x: float = Field(..., description="插入点 X 坐标（AutoCAD 图纸坐标，mm）")
    y: float = Field(..., description="插入点 Y 坐标（mm）")
    rotation: float = Field(default=0.0, description="旋转角度（弧度），0=水平")
    layer: str | None = Field(None, description="目标图层，None 则使用符号默认图层")
    label: str | None = Field(None, description="设备编号标注，如 T1、QF1")
    scale: float = Field(default=1.0, description="缩放比例，1.0=原始大小")
    attributes: str | None = Field(default=None, description="图块属性 JSON 字符串，如 '{\"RATED_V\":\"220V\"}'，可留空")


class InsertElementTool(BaseTool):
    """
    LangChain Tool：向 AutoCAD 插入电气图元

    根据 symbol_id 查找对应图块名称，调用 AutoCAD COM 接口插入图块，
    并可选地添加设备标注。
    """

    # CanvasState 注入（由 DrawAgent 在构建工具时设置）
    canvas_state: object = Field(default=None, exclude=True)

    name: str = "insert_element"
    description: str = (
        "向 AutoCAD 当前图纸中插入电气图元（图块）。\n"
        "输入图元 symbol_id、坐标位置和设备编号。\n"
        "返回图元 Handle，可用于后续的连接和标注操作。\n\n"
        "## 可用图元符号列表（symbol_id）\n"
        "- CB_3P: 三相断路器 (断路器、保护)\n"
        "- DS_3P: 三相隔离开关 (隔离开关)\n"
        "- TR_2W: 双绕组变压器 (变压器)\n"
        "- BUS_3P: 三相母线 (汇流排)\n"
        "- GND: 接地符号\n"
        "- LA: 避雷器\n"
        "- CT: 电流互感器\n"
        "- VT: 电压互感器\n"
        "- SWGR: 开关柜 (配电柜)\n"
        "- CABLE: 电力电缆\n"
        "- WIRE: 导线/连接线\n"
        "- FUSE: 熔断器\n"
        "- KM: 接触器\n"
        "- MOTOR: 三相异步电动机\n"
        "- GEN: 发电机\n"
        "- RECT: 整流器\n"
        "- BAT: 蓄电池组\n"
        "- CAP: 电容器组\n"
        "- REACT: 电抗器\n"
        "- AMMETER: 电流表\n\n"
        "注意：symbol_id 必须精确匹配上述列表中的值，区分大小写。"
        "例如母线用 BUS_3P（不是 BUS），导线用 WIRE（不是 Line）。"
    )
    args_schema: type[BaseModel] = InsertElementInput

    def _run(
        self,
        symbol_id: str,
        x: float,
        y: float,
        rotation: float = 0.0,
        layer: str | None = None,
        label: str | None = None,
        scale: float = 1.0,
        attributes: dict | None = None,
    ) -> str:
        """
        执行图元插入操作

        Returns:
            操作结果描述字符串
        """
        try:
            from autocad.annotation_ops import annotation_ops
            from autocad.drawing_ops import drawing_ops
            from autocad.layer_manager import layer_manager
            from knowledge.symbol_library import SymbolLibrary
            from models.session import get_session_local

            # 查询符号定义
            db = get_session_local()()
            try:
                lib = SymbolLibrary(db)
                symbol = lib.get_by_id(symbol_id)
                if not symbol:
                    return f"错误：图元符号 '{symbol_id}' 不存在，请检查 symbol_id 是否正确"

                target_layer = layer or symbol.layer
                block_name = symbol.block_name or symbol_id

                # 确保图层存在
                layer_manager.ensure_layer(target_layer)

            finally:
                db.close()

            # 执行插入
            # 注意：不使用 AutoCADTransaction，因为事务用 autocad_connection.doc（心跳线程），
            # 而 create_simple_symbol 在当前线程重新 GetActiveObject，Undo 标记跨线程无效
            handle = drawing_ops.create_simple_symbol(
                symbol_type=symbol_id,
                x=x,
                y=y,
                label=label,
                layer=target_layer,
            )
            label_already_set = True  # create_simple_symbol 已添加标注

            # 添加设备编号标注（如果 create_simple_symbol 未设置）
            if label and not label_already_set:
                annotation_ops.add_text(
                    text=label,
                    x=x + 2,
                    y=y - 5,  # 标注在图元下方
                    height=3.5,
                    layer="ELEC-TEXT",
                )

            logger.info(f"InsertElement success: {symbol_id} at ({x},{y}) handle={handle}")

            # ── 更新 CanvasState ──────────────────────────────
            if self.canvas_state is not None:
                self.canvas_state.record_device(
                    handle=handle,
                    symbol_id=symbol_id,
                    x=x, y=y,
                    label=label,
                    layer=target_layer,
                    rotation=rotation,
                    scale=scale,
                )

            return (
                f"成功插入 {symbol.name}（{symbol_id}）于坐标 ({x:.1f}, {y:.1f})，"
                f"图层: {target_layer}，Handle: {handle}"
                + (f"，标注: {label}" if label else "")
            )

        except ConnectionError:
            return "错误：AutoCAD 未连接，请先在右侧面板点击「连接 AutoCAD」"
        except Exception as e:
            logger.error(f"InsertElement failed: {e}")
            return f"插入图元失败: {e}"

    async def _arun(self, **kwargs) -> str:
        """异步版本（转同步执行）"""
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: self._run(**kwargs))
