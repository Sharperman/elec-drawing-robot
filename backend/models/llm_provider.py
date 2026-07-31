"""
LLM Provider ORM 模型
支持多个供应商独立配置，统一供应商以 model 区分，保留最新 API Key
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.session import Base


class LLMProvider(Base):
    """
    LLM 供应商配置

    设计原则：
    - 同一供应商（base_url）下可有多个 model 条目
    - 同一 (base_url, model) 组合唯一，新写入覆盖旧 API Key（upsert）
    - is_primary: 主力 LLM（文本推理），只能有一个激活
    - is_vision: 多模态 LLM（视觉分析），只能有一个激活
    """
    __tablename__ = "llm_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider_name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
        comment="供应商名称（用户自定义，如 OpenAI / MiMo / DeepSeek）",
    )
    base_url: Mapped[str] = mapped_column(
        String(500), nullable=False,
        comment="API Base URL（OpenAI 兼容格式，如 https://api.openai.com/v1）",
    )
    api_key: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="API Key（存储原始值，前端展示时消隐）",
    )
    model: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="模型名称（如 gpt-4o / mimo-v2.5 / deepseek-v3）",
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
        comment="是否为主力 LLM（文本推理用），全表只能有一个 True",
    )
    is_vision: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True,
        comment="是否为多模态 LLM（视觉分析用），全表只能有一个 True",
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=True,
        comment="最大输出 token 数（null 表示不限制，由模型决定）",
    )
    temperature: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="默认温度参数（0.0-2.0）",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="是否启用",
    )
    last_tested_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True,
        comment="最后测试连接时间",
    )
    test_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        comment="测试连接状态: ok / fail / unknown",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow, server_default=func.now(),
    )

    def mask_key(self) -> str:
        """返回消隐后的 API Key（仅显示前后4位）"""
        if len(self.api_key) <= 8:
            return "*" * len(self.api_key)
        return self.api_key[:4] + "*" * (len(self.api_key) - 8) + self.api_key[-4:]

    def to_dict(self, mask_key: bool = True) -> dict:
        return {
            "id": self.id,
            "provider_name": self.provider_name,
            "base_url": self.base_url,
            "api_key": self.mask_key() if mask_key else self.api_key,
            "model": self.model,
            "is_primary": self.is_primary,
            "is_vision": self.is_vision,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "is_active": self.is_active,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "test_status": self.test_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self) -> str:
        return f"<LLMProvider id={self.id} provider={self.provider_name!r} model={self.model!r} primary={self.is_primary} vision={self.is_vision}>"
