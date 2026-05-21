"""
所有 API 请求/响应 Pydantic v2 Schema
"""
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


# ============================================================
# 通用响应结构
# ============================================================

class ApiResponse(BaseModel):
    """标准 API 响应包装"""
    code: int = Field(default=0, description="错误码，0=成功")
    message: str = Field(default="success")
    data: Any = Field(default=None)


class PagedResponse(BaseModel):
    """分页响应"""
    total: int
    page: int
    page_size: int
    items: list[Any]


# ============================================================
# Chat / Session Schema
# ============================================================

class ChatRequest(BaseModel):
    """发送对话消息请求"""
    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., min_length=1, max_length=4096, description="用户消息")
    image_data: Optional[str] = Field(None, description="附带图片的 base64 数据")
    stream: bool = Field(default=True, description="是否使用 SSE 流式响应")


class ChatConfirmRequest(BaseModel):
    """确认执行 Agent 计划请求"""
    session_id: str
    confirm: bool = Field(..., description="true=确认执行，false=取消")
    modifications: Optional[str] = Field(None, description="用户对计划的修改说明")


class MessageSchema(BaseModel):
    """消息 Schema"""
    id: int
    session_id: str
    role: str
    content: str
    tool_calls: Optional[str] = None
    image_data: Optional[str] = None
    is_streaming: bool = False
    token_count: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionSchema(BaseModel):
    """会话 Schema"""
    id: int
    session_id: str
    title: str
    drawing_file: Optional[str] = None
    drawing_name: Optional[str] = None
    standard_id: Optional[int] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreateSessionRequest(BaseModel):
    """创建会话请求"""
    title: str = Field(default="新建会话", max_length=200)
    drawing_file: Optional[str] = None
    standard_id: Optional[int] = None


# ============================================================
# Recognition Schema
# ============================================================

class RecognitionRequest(BaseModel):
    """图片识别请求"""
    image_data: str = Field(..., description="图片的 base64 编码")
    session_id: Optional[str] = Field(None)


class DetectedElement(BaseModel):
    """识别出的单个电气元件"""
    symbol_id: str
    symbol_name: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    bbox: list[float] = Field(..., description="边界框 [x1, y1, x2, y2]（归一化坐标）")
    center_x: float
    center_y: float
    width: float
    height: float


class RecognitionResponse(BaseModel):
    """图片识别响应"""
    elements: list[DetectedElement]
    total: int
    model_version: str
    inference_time_ms: float


# ============================================================
# AutoCAD Schema
# ============================================================

class AutoCADStatusResponse(BaseModel):
    """AutoCAD 连接状态"""
    connected: bool
    drawing_name: Optional[str] = None
    drawing_path: Optional[str] = None
    autocad_version: Optional[str] = None
    entity_count: int = 0
    last_check: datetime


class AutoCADConnectRequest(BaseModel):
    """连接 AutoCAD 请求"""
    version: Optional[str] = Field(None, description="AutoCAD ProgID，如 AutoCAD.Application.25")


# ============================================================
# Symbol Schema
# ============================================================

class SymbolSchema(BaseModel):
    """图元符号 Schema"""
    id: int
    symbol_id: str
    name: str
    name_en: str
    category: str
    standard: str
    description: str
    block_name: str
    layer: str
    width: float
    height: float
    tags: str  # JSON 字符串
    is_builtin: bool
    is_active: bool

    model_config = {"from_attributes": True}


class CreateSymbolRequest(BaseModel):
    """创建图元符号请求"""
    symbol_id: str = Field(..., min_length=1, max_length=50)
    name: str = Field(..., min_length=1, max_length=100)
    name_en: str = Field(default="", max_length=100)
    category: str = Field(default="general")
    description: str = Field(default="")
    block_name: str = Field(default="")
    layer: str = Field(default="ELEC-SYMBOL")
    width: float = Field(default=1.0, gt=0)
    height: float = Field(default=1.0, gt=0)
    tags: list[str] = Field(default_factory=list)


class UpdateSymbolRequest(BaseModel):
    """更新图元符号请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    block_name: Optional[str] = None
    layer: Optional[str] = None
    tags: Optional[list[str]] = None
    is_active: Optional[bool] = None


# ============================================================
# Standards Schema
# ============================================================

class LayerConfigSchema(BaseModel):
    """图层配置 Schema"""
    id: int
    standard_id: int
    layer_name: str
    color_index: int
    linetype: str
    lineweight: float
    description: str

    model_config = {"from_attributes": True}


class DrawingStandardSchema(BaseModel):
    """绘图规范 Schema"""
    id: int
    name: str
    description: str
    version: str
    is_active: bool
    text_style: str
    text_height: float
    dim_style: str
    title_block: str
    created_at: datetime
    layers: list[LayerConfigSchema] = []

    model_config = {"from_attributes": True}


class CreateStandardRequest(BaseModel):
    """创建绘图规范请求"""
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="")
    version: str = Field(default="1.0")
    text_style: str = Field(default="Standard")
    text_height: float = Field(default=3.5, gt=0)
    dim_style: str = Field(default="Standard")
    title_block: dict = Field(default_factory=dict)


class UpdateStandardRequest(BaseModel):
    """更新绘图规范请求"""
    name: Optional[str] = None
    description: Optional[str] = None
    version: Optional[str] = None
    text_style: Optional[str] = None
    text_height: Optional[float] = None
    is_active: Optional[bool] = None


class ActivateStandardRequest(BaseModel):
    """激活规范请求"""
    standard_id: int


# ============================================================
# Feedback Schema
# ============================================================

class FeedbackRequest(BaseModel):
    """提交用户反馈请求"""
    session_id: str
    message_id: Optional[int] = None
    feedback_type: str = Field(..., description="positive/negative/correction/suggestion")
    original_input: str = Field(default="")
    agent_output: str = Field(default="")
    user_comment: str = Field(default="", max_length=2000)
    correction: Optional[str] = Field(None, max_length=2000)
    rating: Optional[int] = Field(None, ge=1, le=5)

    @field_validator("feedback_type")
    @classmethod
    def validate_feedback_type(cls, v: str) -> str:
        allowed = {"positive", "negative", "correction", "suggestion"}
        if v not in allowed:
            raise ValueError(f"feedback_type must be one of {allowed}")
        return v


class LearnedRuleSchema(BaseModel):
    """学习规则 Schema"""
    id: int
    rule_id: str
    title: str
    rule_content: str
    trigger_pattern: str
    confidence: float
    apply_count: int
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
