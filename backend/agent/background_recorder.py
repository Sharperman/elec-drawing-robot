"""
CAD 操作录制引擎
定期截图 + COM 状态采样 → 差量检测 → OperationStep
"""
import threading
import time

from loguru import logger


class BackgroundRecorder:
    """
    后台录制引擎
    - 截图（由 VideoRecorder 完成）
    - COM 状态采样（每5秒）
    - 差量检测 → OperationStep
    """

    def __init__(self):
        self._session_id: int | None = None
        self._running = False
        self._sampler_thread: threading.Thread | None = None
        self._steps: list = []  # 内存中的步骤列表
        self._last_entities: dict = {}  # {handle: type} 上一帧快照
        self._start_time = 0
        self._db_session = None
        self._com_available = False

    def start(self, session_id: int, session_name: str = "", cad_file: str = ""):
        """开始录制"""
        if self._running:
            return False

        self._session_id = session_id
        self._running = True
        self._steps.clear()
        self._last_entities.clear()
        self._start_time = time.time()

        # 初始化 COM
        try:
            from autocad.connection import autocad_connection
            if autocad_connection.is_connected:
                self._com_available = True
                # 初始快照
                self._snapshot_cad_state()
        except Exception as e:
            logger.warning(f"CAD COM 初始化失败，仅录制视频: {e}")
            self._com_available = False

        # 启动采样线程
        self._sampler_thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._sampler_thread.start()

        logger.info(f"录制引擎启动: session_id={session_id}")
        return True

    def stop(self) -> list:
        """停止录制，返回步骤列表"""
        self._running = False
        if self._sampler_thread:
            self._sampler_thread.join(timeout=3)

        steps = self._steps.copy()
        logger.info(f"录制引擎停止: {len(steps)} 个步骤")
        return steps

    def _sample_loop(self):
        """采样线程主循环"""
        while self._running:
            time.sleep(5)
            if not self._running:
                break
            try:
                self._sample_once()
            except Exception as e:
                logger.warning(f"采样出错: {e}")

    def _sample_once(self):
        """单次采样：检测 CAD 实体变化"""
        if not self._com_available:
            self._steps.append({
                "timestamp": time.time() - self._start_time,
                "step_type": "idle",
                "entities": [],
                "description": "CAD 未连接，无实体数据",
            })
            return

        try:
            from autocad.connection import autocad_connection
            doc = autocad_connection.doc
            new_entities = {}

            for entity in doc.ModelSpace:
                try:
                    handle = entity.Handle
                    entity_type = entity.ObjectName if hasattr(entity, 'ObjectName') else str(type(entity).__name__)
                    new_entities[handle] = entity_type
                except Exception:
                    continue

            # 差量检测
            added = {k: v for k, v in new_entities.items() if k not in self._last_entities}
            removed = {k: v for k, v in self._last_entities.items() if k not in new_entities}

            if added:
                self._steps.append({
                    "timestamp": time.time() - self._start_time,
                    "step_type": "add",
                    "entities": [{"handle": k, "type": v} for k, v in list(added.items())[:20]],
                    "description": f"新增 {len(added)} 个实体",
                })
            if removed:
                self._steps.append({
                    "timestamp": time.time() - self._start_time,
                    "step_type": "delete",
                    "entities": [{"handle": k, "type": v} for k, v in list(removed.items())[:20]],
                    "description": f"删除 {len(removed)} 个实体",
                })

            self._last_entities = new_entities

        except Exception as e:
            self._steps.append({
                "timestamp": time.time() - self._start_time,
                "step_type": "error",
                "entities": [],
                "description": f"采样出错: {str(e)[:100]}",
            })

    def _snapshot_cad_state(self):
        """获取当前 CAD 状态快照"""
        try:
            from autocad.connection import autocad_connection
            doc = autocad_connection.doc
            for entity in doc.ModelSpace:
                try:
                    handle = entity.Handle
                    entity_type = entity.ObjectName if hasattr(entity, 'ObjectName') else str(type(entity).__name__)
                    self._last_entities[handle] = entity_type
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"CAD 快照失败: {e}")


# 全局单例
background_recorder = BackgroundRecorder()
