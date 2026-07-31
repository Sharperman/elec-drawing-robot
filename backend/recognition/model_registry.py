"""
模型版本注册表
管理 YOLOv8 模型的版本、路径和热更新
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
from pathlib import Path

from loguru import logger


@dataclass
class ModelInfo:
    """模型信息"""
    name: str
    path: str
    version: str
    accuracy: float = 0.0
    classes: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    is_active: bool = False


class ModelRegistry:
    """
    YOLOv8 模型版本注册表

    管理多个模型版本，支持热切换活跃模型。
    注册表持久化到 JSON 文件。
    """

    def __init__(self) -> None:
        from config import settings
        self._models_dir = Path(settings.YOLO_MODEL_PATH).parent
        self._registry_file = self._models_dir / "model_registry.json"
        self._registry: dict[str, ModelInfo] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """从 JSON 文件加载注册表"""
        self._models_dir.mkdir(parents=True, exist_ok=True)

        if self._registry_file.exists():
            try:
                with open(self._registry_file, encoding="utf-8") as f:
                    data = json.load(f)
                for name, info in data.items():
                    self._registry[name] = ModelInfo(**info)
                logger.debug(f"Model registry loaded: {len(self._registry)} models")
            except Exception as e:
                logger.warning(f"Failed to load model registry: {e}")
        else:
            # 扫描模型目录中的 .pt 文件
            self._scan_models()

    def _save_registry(self) -> None:
        """保存注册表到 JSON 文件"""
        try:
            data = {name: asdict(info) for name, info in self._registry.items()}
            with open(self._registry_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save model registry: {e}")

    def _scan_models(self) -> None:
        """扫描模型目录，自动注册 .pt 和 .onnx 文件"""
        for ext in ["*.pt", "*.onnx"]:
            for model_path in self._models_dir.glob(ext):
                name = model_path.stem
                if name not in self._registry:
                    self._registry[name] = ModelInfo(
                        name=name,
                        path=str(model_path),
                        version=name,
                        is_active=name == "elec_symbol_yolov8",
                    )
        self._save_registry()

    def register(
        self,
        name: str,
        path: str,
        version: str,
        accuracy: float = 0.0,
        classes: list[str] | None = None,
    ) -> ModelInfo:
        """
        注册新模型

        Args:
            name: 模型名称
            path: 模型文件路径
            version: 版本号
            accuracy: 验证集精度
            classes: 检测类别列表

        Returns:
            ModelInfo 实例
        """
        info = ModelInfo(
            name=name,
            path=path,
            version=version,
            accuracy=accuracy,
            classes=classes or [],
        )
        self._registry[name] = info
        self._save_registry()
        logger.info(f"Model registered: {name} v{version} at {path}")
        return info

    def activate(self, name: str) -> bool:
        """
        激活指定模型（热切换）

        Args:
            name: 模型名称

        Returns:
            是否激活成功
        """
        if name not in self._registry:
            logger.error(f"Model '{name}' not found in registry")
            return False

        # 取消其他模型的激活状态
        for info in self._registry.values():
            info.is_active = False

        # 激活目标模型
        self._registry[name].is_active = True
        self._save_registry()

        # 触发检测器重新加载
        from recognition.detector import detector
        detector._model = None
        detector._model_loaded = False
        logger.info(f"Model activated: {name}")
        return True

    def get_active(self) -> ModelInfo | None:
        """获取当前激活的模型信息"""
        for info in self._registry.values():
            if info.is_active:
                return info
        return None

    def list_all(self) -> list[ModelInfo]:
        """列出所有注册的模型"""
        return list(self._registry.values())

    def get(self, name: str) -> ModelInfo | None:
        """通过名称获取模型信息"""
        return self._registry.get(name)


# 全局单例
model_registry = ModelRegistry()
