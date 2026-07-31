"""
用户反馈和学习规则 ORM 模型
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from models.session import Base


class UserFeedback(Base):
    """用户反馈记录"""
    __tablename__ = "user_feedbacks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="来源会话 ID"
    )
    message_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="关联的消息 ID"
    )
    feedback_type: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="反馈类型：positive/negative/correction/suggestion"
    )
    original_input: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="用户原始输入"
    )
    agent_output: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="Agent 的输出（操作结果）"
    )
    user_comment: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="用户反馈说明"
    )
    correction: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="用户提供的正确做法（纠错类反馈）"
    )
    rating: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="满意度评分（1-5）"
    )
    is_processed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否已被处理（提炼为规则）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserFeedback id={self.id} type={self.feedback_type!r}>"


class LearnedRule(Base):
    """从用户反馈中提炼的学习规则"""
    __tablename__ = "learned_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="规则唯一标识（UUID）"
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False,
        comment="规则标题（简洁描述）"
    )
    rule_content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="规则内容（LLM 提炼的自然语言描述）"
    )
    trigger_pattern: Mapped[str] = mapped_column(
        Text, nullable=False, default="",
        comment="触发该规则的用户意图模式"
    )
    source_feedback_ids: Mapped[str] = mapped_column(
        Text, nullable=False, default="[]",
        comment="来源反馈 ID 列表（JSON 字符串）"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0,
        comment="规则置信度（0.0-1.0）"
    )
    apply_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="规则被应用次数"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="规则是否生效"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow, server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<LearnedRule id={self.id} title={self.title!r}>"
