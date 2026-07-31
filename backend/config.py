"""
应用配置管理
使用 pydantic-settings 从 .env 文件读取配置
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# 关键路径常量
ROOT_DIR = Path(__file__).parent.parent                        # elec-drawing-robot/
DATA_DIR = Path(__file__).parent / "data"                       # backend/data/（统一数据目录）
LOG_DIR_DEFAULT = ROOT_DIR / "logs"                             # 日志目录
YOLO_MODEL_DIR = Path(__file__).parent / "recognition" / "models"


class Settings(BaseSettings):
    """应用配置，所有字段均可通过环境变量覆盖"""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ---- OpenAI / LLM ----
    OPENAI_API_KEY: str = Field(default="", description="OpenAI API Key")
    OPENAI_BASE_URL: str = Field(
        default="https://api.openai.com/v1",
        description="OpenAI 兼容接口地址，可替换为代理或本地部署",
    )
    MODEL_NAME: str = Field(default="gpt-4o", description="主 LLM 模型名称")
    EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="Embedding 模型名称",
    )
    LLM_TEMPERATURE: float = Field(default=1.0, ge=0.0, le=2.0)
    LLM_MAX_TOKENS: int = Field(default=16384, ge=256, le=2097152)

    # ---- Vision LLM（多模态） ----
    VISION_MODEL_NAME: str = Field(default="", description="多模态 LLM 模型名称（空则 fallback 到 MODEL_NAME）")
    VISION_API_KEY: str = Field(default="", description="多模态 LLM API Key（空则 fallback 到 OPENAI_API_KEY）")
    VISION_BASE_URL: str = Field(default="", description="多模态 LLM API 地址（空则 fallback 到 OPENAI_BASE_URL）")

    # ---- 服务器 ----
    PORT: int = Field(default=8765, description="FastAPI 监听端口")
    CORS_ORIGINS: list[str] = Field(
        default=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8765",
            "http://127.0.0.1:8765",
            "null",
        ],
        description="允许的跨域来源",
    )

    # ---- 数据库 ----
    DB_PATH: str = Field(
        default=str(DATA_DIR / "db" / "elec_robot.db"),
        description="SQLite 数据库文件路径",
    )

    # ---- ChromaDB ----
    CHROMA_PATH: str = Field(
        default=str(DATA_DIR / "chroma"),
        description="ChromaDB 持久化目录",
    )
    CHROMA_COLLECTION_STANDARDS: str = Field(
        default="drawing_standards",
        description="规范知识库 Collection 名称",
    )
    CHROMA_COLLECTION_SYMBOLS: str = Field(
        default="symbol_descriptions",
        description="图元描述 Collection 名称",
    )

    # ---- AutoCAD ----
    AUTOCAD_VERSION: str = Field(
        default="AutoCAD.Application",
        description="AutoCAD COM ProgID，如 AutoCAD.Application.25",
    )
    AUTOCAD_RECONNECT_INTERVAL: int = Field(
        default=30, description="AutoCAD 心跳检测间隔（秒）"
    )
    AUTOCAD_MAX_RETRY: int = Field(default=3, description="COM 操作最大重试次数")

    # ---- YOLOv8 ----
    YOLO_MODEL_PATH: str = Field(
        default=str(YOLO_MODEL_DIR / "elec_symbol_yolov8.pt"),
        description="YOLOv8 模型文件路径",
    )
    YOLO_CONFIDENCE_THRESHOLD: float = Field(
        default=0.5, ge=0.0, le=1.0, description="检测置信度阈值"
    )
    YOLO_IOU_THRESHOLD: float = Field(
        default=0.45, ge=0.0, le=1.0, description="NMS IoU 阈值"
    )
    YOLO_IMG_SIZE: int = Field(default=640, description="推理图像尺寸")
    YOLO_DEVICE: str = Field(default="cpu", description="推理设备: cpu / cuda / mps")

    # ---- 日志 ----
    LOG_LEVEL: str = Field(default="INFO", description="日志级别")
    LOG_DIR: str = Field(default=str(LOG_DIR_DEFAULT), description="日志文件目录")
    LOG_ROTATION: str = Field(default="10 MB", description="日志文件轮转阈值")
    LOG_RETENTION: str = Field(default="30 days", description="日志保留周期")

    # ---- Agent ----
    AGENT_MAX_ITERATIONS: int = Field(default=10, description="Agent 最大迭代轮次")
    AGENT_VERBOSE: bool = Field(default=False, description="是否输出 Agent 思考链")

    # ---- 反馈学习 ----
    FEEDBACK_REFINE_THRESHOLD: int = Field(
        default=5, description="累积多少条反馈后触发规则提炼"
    )

    # ---- 文件上传 ----
    UPLOAD_DIR: str = Field(
        default=str(DATA_DIR / "uploads"),
        description="文件上传目录（参考图纸等）",
    )

    # ---- 学习模式 ----
    LEARN_THUMB_DIR: str = Field(
        default=str(DATA_DIR / "pattern_thumbnails"),
        description="学习模式缩略图目录",
    )


# 全局单例
settings = Settings()

# 确保数据目录存在
for _dir in [settings.DB_PATH, settings.CHROMA_PATH, settings.LOG_DIR, settings.UPLOAD_DIR, settings.LEARN_THUMB_DIR]:
    p = Path(_dir)
    if "." in p.name:
        p = p.parent  # 文件路径取其父目录
    p.mkdir(parents=True, exist_ok=True)

# 启动时配置校验（P2-9）

_errors = []
if not settings.OPENAI_API_KEY:
    _errors.append("OPENAI_API_KEY 未设置，LLM 功能将不可用")
if not settings.OPENAI_BASE_URL:
    _errors.append("OPENAI_BASE_URL 未设置")
if not settings.MODEL_NAME:
    _errors.append("MODEL_NAME 未设置")

if _errors:
    import logging
    _log = logging.getLogger("config")
    for err in _errors:
        _log.warning(f"⚠️  配置警告: {err}")
