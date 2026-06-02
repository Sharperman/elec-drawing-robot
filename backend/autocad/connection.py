"""
AutoCAD COM 连接管理
单例模式，支持心跳检测和自动重连
"""
import threading
from typing import Optional

from loguru import logger


class AutoCADConnection:
    """
    AutoCAD COM 连接管理器（单例）
    
    通过 win32com.client 连接到运行中的 AutoCAD 进程，
    获取 Application、ActiveDocument 和 ModelSpace 对象。
    """

    _instance: Optional["AutoCADConnection"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "AutoCADConnection":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._acad = None          # win32com Application 对象
        self._doc = None           # ActiveDocument
        self._model_space = None   # ModelSpace
        self._is_connected: bool = False
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_heartbeat: threading.Event = threading.Event()

    # ============================================================
    # 连接管理
    # ============================================================

    def connect(self, version: Optional[str] = None) -> bool:
        """
        连接到正在运行的 AutoCAD 进程

        Args:
            version: AutoCAD COM ProgID，如 'AutoCAD.Application.25'
                    为 None 时使用配置文件中的版本

        Returns:
            连接是否成功
        """
        try:
            import pythoncom
            pythoncom.CoInitialize()
            import win32com.client  # type: ignore

            from config import settings
            prog_id = version or settings.AUTOCAD_VERSION

            logger.info(f"Connecting to AutoCAD: {prog_id}")
            self._acad = win32com.client.GetActiveObject(prog_id)
            self._acad.Visible = True

            # 获取活动文档
            if self._acad.Documents.Count == 0:
                raise RuntimeError("AutoCAD 中没有打开的图纸")

            self._doc = self._acad.ActiveDocument
            self._model_space = self._doc.ModelSpace
            self._is_connected = True

            logger.info(
                f"AutoCAD connected: {self._acad.Version}, "
                f"Drawing: {self._doc.Name}"
            )

            # 启动心跳检测
            self._start_heartbeat()
            return True

        except ImportError:
            logger.error("pywin32 not installed. AutoCAD COM is not available.")
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(f"AutoCAD connection failed: {e}")
            self._is_connected = False
            return False

    def disconnect(self) -> None:
        """断开 AutoCAD 连接"""
        self._stop_heartbeat.set()
        self._is_connected = False
        self._acad = None
        self._doc = None
        self._model_space = None
        logger.info("AutoCAD disconnected")

    def reconnect(self, version: Optional[str] = None) -> bool:
        """重新连接 AutoCAD"""
        logger.info("Attempting to reconnect AutoCAD...")
        self.disconnect()
        return self.connect(version)

    # ============================================================
    # 属性访问
    # ============================================================

    @property
    def is_connected(self) -> bool:
        """返回连接状态"""
        return self._is_connected

    @property
    def acad(self):
        """获取 AutoCAD Application 对象"""
        self._ensure_connected()
        return self._acad

    @property
    def doc(self):
        """获取 ActiveDocument"""
        self._ensure_connected()
        return self._doc

    @property
    def model_space(self):
        """获取 ModelSpace"""
        self._ensure_connected()
        return self._model_space

    def get_status(self) -> dict:
        """
        获取当前连接状态信息

        Returns:
            包含连接状态的字典
        """
        from datetime import datetime

        if not self._is_connected or self._acad is None:
            return {
                "connected": False,
                "drawing_name": None,
                "drawing_path": None,
                "autocad_version": None,
                "entity_count": 0,
                "last_check": datetime.utcnow(),
            }

        try:
            return {
                "connected": True,
                "drawing_name": self._doc.Name,
                "drawing_path": self._doc.FullName,
                "autocad_version": str(self._acad.Version),
                "entity_count": self._model_space.Count,
                "last_check": datetime.utcnow(),
            }
        except Exception:
            self._is_connected = False
            return {
                "connected": False,
                "drawing_name": None,
                "drawing_path": None,
                "autocad_version": None,
                "entity_count": 0,
                "last_check": datetime.utcnow(),
            }

    # ============================================================
    # 内部方法
    # ============================================================

    def _ensure_connected(self) -> None:
        """确保已连接，未连接则抛出异常"""
        if not self._is_connected:
            from utils.error_codes import ErrorCode
            raise ConnectionError(
                f"AutoCAD not connected (code={ErrorCode.AUTOCAD_NOT_CONNECTED})"
            )

    def _heartbeat_loop(self) -> None:
        """心跳检测线程：定期检查 AutoCAD 连接状态
        
        注意：心跳线程运行在独立线程中，必须重新 GetActiveObject 获取
        当前线程的 COM dispatch，不能使用 connect() 线程中的 self._acad，
        否则会违反 COM STA 规则导致 "未找到主键" 等错误。
        """
        from config import settings
        interval = settings.AUTOCAD_RECONNECT_INTERVAL

        while not self._stop_heartbeat.wait(timeout=interval):
            if not self._is_connected:
                break
            try:
                # 在当前线程重新获取 COM dispatch（避免跨线程 STA 冲突）
                import pythoncom
                pythoncom.CoInitialize()
                import win32com.client
                acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
                _ = acad.Version  # 验证连接存活
            except Exception as e:
                logger.warning(f"AutoCAD heartbeat failed, marking disconnected: {e}")
                self._is_connected = False
                break

    def _start_heartbeat(self) -> None:
        """启动心跳检测线程"""
        self._stop_heartbeat.clear()
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name="autocad-heartbeat",
        )
        self._heartbeat_thread.start()


# 全局单例
autocad_connection = AutoCADConnection()
