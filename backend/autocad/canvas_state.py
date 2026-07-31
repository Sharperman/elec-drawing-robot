"""
CanvasState — 画布状态记忆模块

核心理念：不要让 LLM 记住任何东西，让系统记住一切，
LLM 只负责"在需要的时候查一下"。

每次工具执行后自动更新（由 Tool 内部调用 record_* 方法），
LLM 通过 query_canvas 工具随时查询当前画布状态。

设计原则：
- 纯内存存储（会话级，断开即清）
- 高内聚：只追踪"对绘图决策有用"的信息
- 低侵入：工具内部轻量调用，不影响现有链路
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

# ════════════════════════════════════════════════════════════════
# 数据类
# ════════════════════════════════════════════════════════════════

@dataclass
class CanvasDevice:
    """画布上的一个设备"""
    handle: str
    symbol_id: str                        # e.g., "CB_3P", "TR_2W"
    label: str | None = None           # e.g., "QF1", "T1"
    x: float = 0.0
    y: float = 0.0
    layer: str = "0"
    rotation: float = 0.0
    scale: float = 1.0
    inserted_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def position_key(self) -> str:
        return f"({self.x:.0f},{self.y:.0f})"


@dataclass
class CanvasConnection:
    """设备间连线（母线/导线/电缆）"""
    from_handle: str
    to_handle: str
    from_label: str | None = None
    to_label: str | None = None
    line_type: str = "wire"               # "bus" | "wire" | "cable"
    layer: str = "ELEC-WIRE"
    via_points: list | None = None     # [[x1,y1],[x2,y2],...]
    connected_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class CanvasAnnotation:
    """文字标注"""
    handle: str
    text: str
    x: float = 0.0
    y: float = 0.0
    target_handle: str | None = None   # 标注属于哪个设备
    height: float = 3.5
    annotation_type: str = "text"         # "text" | "dim" | "leader"
    annotated_at: datetime = field(default_factory=datetime.utcnow)


# ════════════════════════════════════════════════════════════════
# CanvasState 追踪器
# ════════════════════════════════════════════════════════════════

class CanvasState:
    """
    每个会话独立的画布状态追踪器

    生命周期：随 DrawAgent 创建，随会话结束销毁。
    所有读取操作都是纯查询，不修改状态。
    所有写入操作（record_*）都是追加/更新，由 Tool._run() 调用。
    """

    # 布局常量
    DEFAULT_H_SPACING: float = 300.0      # 水平设备间距 (mm)
    DEFAULT_V_SPACING: float = 150.0      # 垂直设备间距 (mm)
    DEFAULT_START_X: float = 500.0
    DEFAULT_START_Y: float = 800.0

    def __init__(self, session_id: str, drawing_name: str = "") -> None:
        self.session_id = session_id
        self.drawing_name = drawing_name
        self.devices: list[CanvasDevice] = []
        self.connections: list[CanvasConnection] = []
        self.annotations: list[CanvasAnnotation] = []
        self.version: int = 0

        # 画布边界追踪
        self._min_x: float = float("inf")
        self._max_x: float = float("-inf")
        self._min_y: float = float("inf")
        self._max_y: float = float("-inf")

    # ── 写入 API（由 Tool 调用）──────────────────────────────────

    def record_device(
        self,
        handle: str,
        symbol_id: str,
        x: float,
        y: float,
        label: str | None = None,
        layer: str = "0",
        rotation: float = 0.0,
        scale: float = 1.0,
    ) -> None:
        """记录设备插入"""
        if any(d.handle == handle for d in self.devices):
            logger.debug(f"CanvasState: device {handle} already recorded, skipping")
            return

        self.devices.append(CanvasDevice(
            handle=handle, symbol_id=symbol_id, label=label,
            x=x, y=y, layer=layer, rotation=rotation, scale=scale,
        ))
        self._expand_bounds(x, y)
        self.version += 1
        logger.debug(
            f"CanvasState[{self.session_id}]: +device {symbol_id}"
            + (f" [{label}]" if label else "")
            + f" @ ({x:.0f},{y:.0f}) → v{self.version}"
        )

    def record_connection(
        self,
        from_handle: str,
        to_handle: str,
        line_type: str = "wire",
        layer: str = "ELEC-WIRE",
        via_points: list | None = None,
    ) -> None:
        """记录连线"""
        from_label = self._resolve_label(from_handle)
        to_label = self._resolve_label(to_handle)

        self.connections.append(CanvasConnection(
            from_handle=from_handle, to_handle=to_handle,
            from_label=from_label, to_label=to_label,
            line_type=line_type, layer=layer, via_points=via_points,
        ))
        self.version += 1
        logger.debug(
            f"CanvasState[{self.session_id}]: +connection "
            f"{from_label or from_handle} → {to_label or to_handle} [{line_type}]"
        )

    def record_annotation(
        self,
        handle: str,
        text: str,
        x: float,
        y: float,
        target_handle: str | None = None,
        height: float = 3.5,
        annotation_type: str = "text",
    ) -> None:
        """记录标注"""
        if any(a.handle == handle for a in self.annotations):
            return

        self.annotations.append(CanvasAnnotation(
            handle=handle, text=text, x=x, y=y,
            target_handle=target_handle,
            height=height, annotation_type=annotation_type,
        ))
        self.version += 1

    def record_remove_device(self, handle: str) -> None:
        """记录设备删除"""
        before = len(self.devices)
        target = self.find_device_by_handle(handle)
        self.devices = [d for d in self.devices if d.handle != handle]
        # 级联删除关联连线和标注
        self.connections = [
            c for c in self.connections
            if c.from_handle != handle and c.to_handle != handle
        ]
        self.annotations = [
            a for a in self.annotations
            if a.target_handle != handle
        ]
        after = len(self.devices)
        if before != after:
            self._recalc_bounds()
            self.version += 1
            lbl = f" [{target.label}]" if target and target.label else ""
            logger.debug(
                f"CanvasState[{self.session_id}]: -device {handle}{lbl}"
            )

    def record_update_device(self, handle: str, **updates) -> None:
        """记录设备属性更新（移动/旋转/缩放/图层）"""
        for d in self.devices:
            if d.handle == handle:
                for k, v in updates.items():
                    if hasattr(d, k):
                        setattr(d, k, v)
                if "x" in updates or "y" in updates:
                    self._recalc_bounds()
                self.version += 1
                logger.debug(f"CanvasState[{self.session_id}]: ~device {handle} updated {list(updates.keys())}")
                return
        logger.warning(f"CanvasState: device {handle} not found for update")

    # ── 查询 API（供 query_canvas Tool 调用）─────────────────────

    def get_summary(self) -> str:
        """生成画布状态摘要，LLM 可直接阅读理解"""
        if not self.devices:
            name_hint = f" ({self.drawing_name})" if self.drawing_name else ""
            return f"# 画布状态 (v{self.version}){name_hint}\n\n当前画布为空，尚无任何设备。建议从坐标 ({self.DEFAULT_START_X:.0f}, {self.DEFAULT_START_Y:.0f}) 开始布局。"

        lines = [
            f"# 画布状态 (v{self.version})",
            f"**设备**: {len(self.devices)} | **连线**: {len(self.connections)} | **标注**: {len(self.annotations)}",
            "",
            "## 设备清单",
        ]

        # 按图层分组展示
        by_layer: dict[str, list[CanvasDevice]] = {}
        for d in self.devices:
            by_layer.setdefault(d.layer, []).append(d)

        for layer, devs in sorted(by_layer.items()):
            lines.append(f"\n### {layer}（{len(devs)} 个）")
            for d in devs:
                lbl = f"[{d.label}] " if d.label else ""
                lines.append(f"- {d.symbol_id} {lbl}@ ({d.x:.0f}, {d.y:.0f}) Handle={d.handle}")

        if self.connections:
            lines.append(f"\n## 连线关系（{len(self.connections)} 条）")
            for c in self.connections:
                fl = c.from_label or c.from_handle
                tl = c.to_label or c.to_handle
                via = ""
                if c.via_points:
                    pts = ", ".join(f"({p[0]:.0f},{p[1]:.0f})" for p in c.via_points)
                    via = f" 经 {pts}"
                lines.append(f"- {fl} → {tl} [{c.line_type}]{via}")

        if self.annotations:
            lines.append(f"\n## 标注列表（{len(self.annotations)} 条）")
            for a in self.annotations:
                tgt = f" → {a.target_handle}" if a.target_handle else ""
                lines.append(f"- \"{a.text}\" @ ({a.x:.0f},{a.y:.0f}){tgt}")

        lines.append("")
        lines.append("## 空间信息")
        if self.devices:
            lines.append(f"- 范围: X [{self._min_x:.0f} ~ {self._max_x:.0f}] Y [{self._min_y:.0f} ~ {self._max_y:.0f}]")
            sx = self.suggested_next_x
            sy = self.suggested_next_y
            lines.append(f"- 建议下个设备位置: **({sx:.0f}, {sy:.0f})**")
            lines.append(f"- 水平间距默认 {self.DEFAULT_H_SPACING:.0f}mm，垂直间距默认 {self.DEFAULT_V_SPACING:.0f}mm")

        return "\n".join(lines)

    def find_devices(
        self,
        label: str | None = None,
        symbol_id: str | None = None,
        layer: str | None = None,
    ) -> list[CanvasDevice]:
        """按条件查找设备"""
        results = self.devices
        if label:
            results = [d for d in results if d.label and label.lower() in d.label.lower()]
        if symbol_id:
            results = [d for d in results if d.symbol_id.upper() == symbol_id.upper()]
        if layer:
            results = [d for d in results if d.layer.upper() == layer.upper()]
        return results

    def find_device_by_handle(self, handle: str) -> CanvasDevice | None:
        for d in self.devices:
            if d.handle == handle:
                return d
        return None

    def get_connections_for(self, handle: str) -> list[CanvasConnection]:
        """获取某个设备的所有连线"""
        return [c for c in self.connections if c.from_handle == handle or c.to_handle == handle]

    def find_empty_region(self, width: float = 200, height: float = 200) -> dict:
        """
        查找画布上的空白区域（简单最近邻扩展策略）

        Returns:
            {"x": float, "y": float, "strategy": "right"|"below"|"origin"}
        """
        if not self.devices:
            return {"x": self.DEFAULT_START_X, "y": self.DEFAULT_START_Y, "strategy": "origin"}

        # 策略 1：最右侧设备右侧
        rightmost = self._max_x
        # 策略 2：最底部设备下方
        bottommost = self._min_y

        # 优先水平扩展
        return {
            "x": rightmost + self.DEFAULT_H_SPACING,
            "y": self._max_y,
            "strategy": "right",
        }

    # ── 统计属性 ─────────────────────────────────────────────────

    @property
    def device_count(self) -> int:
        return len(self.devices)

    @property
    def connection_count(self) -> int:
        return len(self.connections)

    @property
    def suggested_next_x(self) -> float:
        if self.devices:
            return self._max_x + self.DEFAULT_H_SPACING
        return self.DEFAULT_START_X

    @property
    def suggested_next_y(self) -> float:
        if self.devices:
            return self._max_y
        return self.DEFAULT_START_Y

    @property
    def voltage_levels(self) -> list[str]:
        """推测图纸电压等级（基于设备类型）"""
        # 简化推断：有 TR_2W 且 label 含 "kV" → 提取电压
        levels = set()
        for d in self.devices:
            if d.symbol_id == "TR_2W" and d.label:
                # 尝试从标注中提取电压信息
                for a in self.annotations:
                    if a.target_handle == d.handle:
                        for token in a.text.replace("/", " ").split():
                            if "kV" in token.upper() or "KV" in token:
                                levels.add(token.upper())
        return sorted(levels)

    # ── 生命周期 ─────────────────────────────────────────────────

    def reset(self) -> None:
        """重置画布状态（新建图纸时调用）"""
        self.devices.clear()
        self.connections.clear()
        self.annotations.clear()
        self._min_x = float("inf")
        self._max_x = float("-inf")
        self._min_y = float("inf")
        self._max_y = float("-inf")
        self.version = 0
        logger.info(f"CanvasState[{self.session_id}]: reset")

    # ── 内部方法 ─────────────────────────────────────────────────

    def _expand_bounds(self, x: float, y: float) -> None:
        self._min_x = min(self._min_x, x)
        self._max_x = max(self._max_x, x)
        self._min_y = min(self._min_y, y)
        self._max_y = max(self._max_y, y)

    def _recalc_bounds(self) -> None:
        self._min_x = float("inf")
        self._max_x = float("-inf")
        self._min_y = float("inf")
        self._max_y = float("-inf")
        for d in self.devices:
            self._expand_bounds(d.x, d.y)

    def _resolve_label(self, handle: str) -> str | None:
        d = self.find_device_by_handle(handle)
        return d.label if d else None


# ════════════════════════════════════════════════════════════════
# 会话级注册表
# ════════════════════════════════════════════════════════════════

_canvas_registry: dict[str, CanvasState] = {}


def get_canvas_state(session_id: str, drawing_name: str = "") -> CanvasState:
    """
    获取或创建会话的 CanvasState

    Args:
        session_id: 会话 ID
        drawing_name: 图纸名称（仅在首次创建时使用）

    Returns:
        CanvasState 实例
    """
    if session_id not in _canvas_registry:
        _canvas_registry[session_id] = CanvasState(session_id, drawing_name)
        logger.info(f"CanvasState created for session: {session_id}")
    return _canvas_registry[session_id]


def destroy_canvas_state(session_id: str) -> None:
    """销毁会话的 CanvasState"""
    if session_id in _canvas_registry:
        del _canvas_registry[session_id]
        logger.info(f"CanvasState destroyed for session: {session_id}")
