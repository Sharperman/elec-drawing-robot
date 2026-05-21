"""
多轮对话上下文管理器
存储/检索当前图纸状态、已插入图元、意图链
"""
import json
from collections import deque
from datetime import datetime
from typing import Any, Optional


class DrawingContextManager:
    """
    管理当前绘图会话的上下文状态：
    - 已插入的图元（Handle → 图元信息）
    - 意图历史链
    - 当前图纸状态快照
    - 待确认的操作计划
    """

    def __init__(self, session_id: str, max_history: int = 50) -> None:
        self.session_id = session_id
        self.max_history = max_history

        # 图元注册表：handle → {symbol_id, name, x, y, layer, label}
        self._entity_registry: dict[str, dict[str, Any]] = {}

        # 意图历史（最近 N 条）
        self._intent_history: deque[dict] = deque(maxlen=max_history)

        # 待确认的操作计划
        self._pending_plan: Optional[str] = None

        # 当前图纸元信息
        self._drawing_meta: dict[str, Any] = {
            "session_id": session_id,
            "drawing_name": None,
            "drawing_path": None,
            "standard_name": None,
            "entity_count": 0,
            "last_updated": datetime.utcnow().isoformat(),
        }

    # ============================================================
    # 图元注册
    # ============================================================

    def register_entity(
        self,
        handle: str,
        symbol_id: str,
        name: str,
        x: float,
        y: float,
        layer: str = "0",
        label: Optional[str] = None,
    ) -> None:
        """注册一个已插入的图元"""
        self._entity_registry[handle] = {
            "handle": handle,
            "symbol_id": symbol_id,
            "name": name,
            "x": x,
            "y": y,
            "layer": layer,
            "label": label,
            "inserted_at": datetime.utcnow().isoformat(),
        }
        self._drawing_meta["entity_count"] = len(self._entity_registry)
        self._drawing_meta["last_updated"] = datetime.utcnow().isoformat()

    def unregister_entity(self, handle: str) -> bool:
        """取消注册（图元被删除时）"""
        if handle in self._entity_registry:
            del self._entity_registry[handle]
            return True
        return False

    def get_entity(self, handle: str) -> Optional[dict[str, Any]]:
        """通过 Handle 获取图元信息"""
        return self._entity_registry.get(handle)

    def find_entity_by_label(self, label: str) -> Optional[dict[str, Any]]:
        """通过设备标签查找图元"""
        for entity in self._entity_registry.values():
            if entity.get("label") == label:
                return entity
        return None

    def get_all_entities(self) -> list[dict[str, Any]]:
        """获取所有注册的图元"""
        return list(self._entity_registry.values())

    # ============================================================
    # 意图历史
    # ============================================================

    def add_intent(self, intent_type: str, user_input: str, result: Optional[str] = None) -> None:
        """记录一条意图"""
        self._intent_history.append(
            {
                "type": intent_type,
                "input": user_input,
                "result": result,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    def get_recent_intents(self, n: int = 5) -> list[dict]:
        """获取最近 n 条意图"""
        history = list(self._intent_history)
        return history[-n:] if n < len(history) else history

    # ============================================================
    # 待确认计划
    # ============================================================

    def set_pending_plan(self, plan: str) -> None:
        """设置待用户确认的操作计划"""
        self._pending_plan = plan

    def get_pending_plan(self) -> Optional[str]:
        """获取待确认的计划"""
        return self._pending_plan

    def clear_pending_plan(self) -> None:
        """清除待确认计划"""
        self._pending_plan = None

    # ============================================================
    # 图纸元信息
    # ============================================================

    def update_drawing_meta(self, **kwargs) -> None:
        """更新图纸元信息"""
        self._drawing_meta.update(kwargs)
        self._drawing_meta["last_updated"] = datetime.utcnow().isoformat()

    def get_drawing_meta(self) -> dict[str, Any]:
        """获取图纸元信息"""
        return dict(self._drawing_meta)

    # ============================================================
    # 序列化（持久化支持）
    # ============================================================

    def to_dict(self) -> dict:
        """序列化为字典"""
        return {
            "session_id": self.session_id,
            "entity_registry": self._entity_registry,
            "intent_history": list(self._intent_history),
            "pending_plan": self._pending_plan,
            "drawing_meta": self._drawing_meta,
        }

    def build_context_summary(self) -> str:
        """
        构建图纸状态摘要字符串，注入 Agent 系统提示词

        Returns:
            当前状态描述字符串
        """
        entity_count = len(self._entity_registry)
        entities_str = ""
        if entity_count > 0:
            entity_lines = []
            for e in list(self._entity_registry.values())[-10:]:  # 最近 10 个
                label_str = f"[{e['label']}] " if e.get("label") else ""
                entity_lines.append(
                    f"  - {label_str}{e['name']}(handle={e['handle']}) "
                    f"at ({e['x']:.1f},{e['y']:.1f}) layer={e['layer']}"
                )
            entities_str = "\n已插入图元（最近10个）：\n" + "\n".join(entity_lines)

        pending_str = ""
        if self._pending_plan:
            pending_str = f"\n⚠️ 待用户确认的操作计划：{self._pending_plan}"

        return (
            f"【当前图纸状态】\n"
            f"图纸名：{self._drawing_meta.get('drawing_name', '未知')}\n"
            f"图元总数：{entity_count}"
            f"{entities_str}"
            f"{pending_str}"
        )


# 上下文管理器注册表（session_id → 实例）
_context_registry: dict[str, DrawingContextManager] = {}


def get_context(session_id: str) -> DrawingContextManager:
    """
    获取或创建会话上下文管理器

    Args:
        session_id: 会话 ID

    Returns:
        DrawingContextManager 实例
    """
    if session_id not in _context_registry:
        _context_registry[session_id] = DrawingContextManager(session_id)
    return _context_registry[session_id]


def clear_context(session_id: str) -> None:
    """清除会话上下文"""
    if session_id in _context_registry:
        del _context_registry[session_id]
