"""
InsertElement Tool
根据 symbol_id 和位置将电气图元插入到 AutoCAD
"""
from typing import Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field

from loguru import logger


class InsertElementInput(BaseModel):
    """InsertElement 工具输入参数"""
    symbol_id: str = Field(..., description="图元符号 ID，如 CB_3P、TR_2W、GND")
    x: float = Field(..., description="插入点 X 坐标（AutoCAD 图纸坐标，mm）")
    y: float = Field(..., description="插入点 Y 坐标（mm）")
    rotation: float = Field(default=0.0, description="旋转角度（弧度），0=水平")
    layer: Optional[str] = Field(None, description="目标图层，None 则使用符号默认图层")
    label: Optional[str] = Field(None, description="设备编号标注，如 T1、QF1")
    scale: float = Field(default=1.0, description="缩放比例，1.0=原始大小")
    attributes: Optional[dict] = Field(default=None, description="图块属性字典")


class InsertElementTool(BaseTool):
    """
    LangChain Tool：向 AutoCAD 插入电气图元

    根据 symbol_id 查找对应图块名称，调用 AutoCAD COM 接口插入图块，
    并可选地添加设备标注。
    """

    name: str = "insert_element"
    description: str = (
        "向 AutoCAD 当前图纸中插入电气图元（图块）。"
        "输入图元 symbol_id（如 CB_3P=断路器，TR_2W=变压器）、坐标位置和设备编号。"
        "返回图元 Handle，可用于后续的连接和标注操作。"
    )
    args_schema: Type[BaseModel] = InsertElementInput

    def _run(
        self,
        symbol_id: str,
        x: float,
        y: float,
        rotation: float = 0.0,
        layer: Optional[str] = None,
        label: Optional[str] = None,
        scale: float = 1.0,
        attributes: Optional[dict] = None,
    ) -> str:
        """
        执行图元插入操作

        Returns:
            操作结果描述字符串
        """
        try:
            from models.session import get_session_local
            from knowledge.symbol_library import SymbolLibrary
            from autocad.drawing_ops import drawing_ops
            from autocad.annotation_ops import annotation_ops
            from autocad.layer_manager import layer_manager
            from autocad.transaction import AutoCADTransaction

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

            # 执行插入（带事务）
            with AutoCADTransaction(f"insert_{symbol_id}") as txn:
                handle = drawing_ops.insert_block(
                    block_name=block_name,
                    x=x,
                    y=y,
                    x_scale=scale,
                    y_scale=scale,
                    rotation=rotation,
                    layer=target_layer,
                    attributes=attributes,
                )

                # 添加设备编号标注
                if label:
                    annotation_ops.add_text(
                        text=label,
                        x=x + 2,
                        y=y - 5,  # 标注在图元下方
                        height=3.5,
                        layer="ELEC-TEXT",
                    )

                txn.commit()

            logger.info(f"InsertElement success: {symbol_id} at ({x},{y}) handle={handle}")
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
