"""
AutoCAD 图层管理操作
ensure_layer, set_layer_color, set_layer_linetype
"""
from autocad.connection import autocad_connection
from autocad.retry import retry_on_com_error
from loguru import logger

# AutoCAD 颜色常量
AUTOCAD_BYLAYER = 256
AUTOCAD_BYBLOCK = 0

# AutoCAD 线宽枚举（win32com 常量）
LINEWEIGHT_MAP: dict[float, int] = {
    0.0: -3,    # ByLayer
    0.05: 0,
    0.09: 1,
    0.13: 2,
    0.15: 3,
    0.18: 4,
    0.2: 5,
    0.25: 6,
    0.3: 7,
    0.35: 8,
    0.4: 9,
    0.5: 10,
    0.53: 11,
    0.6: 12,
    0.7: 13,
    0.8: 14,
    0.9: 15,
    1.0: 16,
    1.06: 17,
    1.2: 18,
    1.4: 19,
    1.58: 20,
    2.0: 21,
    2.11: 22,
}


class LayerManager:
    """AutoCAD 图层管理类"""

    @retry_on_com_error
    def ensure_layer(
        self,
        layer_name: str,
        color_index: int = 7,
        linetype: str = "Continuous",
        lineweight: float = 0.25,
    ) -> None:
        """
        确保图层存在，不存在则创建，存在则验证属性

        Args:
            layer_name: 图层名称（如 ELEC-POWER）
            color_index: AutoCAD 颜色索引（1-255，7=白色/黑色）
            linetype: 线型名称（Continuous/DASHED/CENTER 等）
            lineweight: 线宽（mm），如 0.25/0.35/0.5
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            from config import settings
            import win32com.client  # type: ignore
            acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
            doc = acad.ActiveDocument
            layers = doc.Layers

            # 检查图层是否已存在
            existing_layer = None
            for i in range(layers.Count):
                if layers.Item(i).Name.upper() == layer_name.upper():
                    existing_layer = layers.Item(i)
                    break

            if existing_layer is None:
                # 创建新图层
                new_layer = layers.Add(layer_name)
                new_layer.Color = color_index
                # 线宽设置：acLnWtByLayer = -1, acLnWtByBlock = -2, acLnWtDefault = -3
                # 某些 AutoCAD 版本对整数线宽值有严格校验，先尝试设置，失败则用 ByLayer
                lw_val = LINEWEIGHT_MAP.get(lineweight, -3)
                try:
                    new_layer.Lineweight = lw_val
                except Exception:
                    new_layer.Lineweight = -3  # acLnWtByLayer
                    logger.debug(f"Layer {layer_name}: Lineweight fallback to ByLayer")
                self._load_linetype(linetype)
                new_layer.Linetype = linetype
                logger.info(
                    f"Layer created: {layer_name} color={color_index} "
                    f"linetype={linetype} lw={lineweight}"
                )
            else:
                logger.debug(f"Layer already exists: {layer_name}")

        except Exception as e:
            logger.error(f"ensure_layer failed: {layer_name} error={e}")
            raise RuntimeError(f"图层操作失败: {e}") from e

    @retry_on_com_error
    def set_layer_color(self, layer_name: str, color_index: int) -> bool:
        """
        设置图层颜色

        Args:
            layer_name: 图层名称
            color_index: AutoCAD 颜色索引（1-255）

        Returns:
            是否成功
        """
        try:
            doc = autocad_connection.doc
            layer = doc.Layers.Item(layer_name)
            layer.Color = color_index
            logger.info(f"Layer color set: {layer_name} = {color_index}")
            return True
        except Exception as e:
            logger.error(f"set_layer_color failed: {layer_name} error={e}")
            return False

    @retry_on_com_error
    def set_layer_linetype(self, layer_name: str, linetype: str) -> bool:
        """
        设置图层线型

        Args:
            layer_name: 图层名称
            linetype: 线型名称（如 Continuous/DASHED/CENTER）

        Returns:
            是否成功
        """
        try:
            doc = autocad_connection.doc
            self._load_linetype(linetype)
            layer = doc.Layers.Item(layer_name)
            layer.Linetype = linetype
            logger.info(f"Layer linetype set: {layer_name} = {linetype}")
            return True
        except Exception as e:
            logger.error(f"set_layer_linetype failed: {layer_name} error={e}")
            return False

    def ensure_all_standard_layers(self) -> None:
        """
        根据当前激活规范初始化所有标准图层
        （启动时或切换规范时调用）
        """
        from knowledge.standards_manager import StandardsManager
        from models.session import get_session_local

        db = get_session_local()()
        try:
            manager = StandardsManager(db)
            standard = manager.get_active()
            if not standard:
                logger.warning("No active standard found, skipping layer initialization")
                return

            for layer in standard.layers:
                self.ensure_layer(
                    layer_name=layer.layer_name,
                    color_index=layer.color_index,
                    linetype=layer.linetype,
                    lineweight=layer.lineweight,
                )
            logger.info(f"All standard layers ensured for: {standard.name}")
        finally:
            db.close()

    def _load_linetype(self, linetype_name: str) -> None:
        """加载线型（如未加载则从 acadiso.lin 加载）"""
        if linetype_name == "Continuous":
            return
        try:
            doc = autocad_connection.doc
            linetypes = doc.Linetypes
            # 检查是否已加载
            for i in range(linetypes.Count):
                if linetypes.Item(i).Name.upper() == linetype_name.upper():
                    return
            # 加载线型（True=覆盖已有）
            linetypes.Load(linetype_name, "acadiso.lin")
        except Exception as e:
            logger.warning(f"Failed to load linetype '{linetype_name}': {e}")


# 全局单例
layer_manager = LayerManager()
