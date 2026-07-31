"""
绘图会话和对话消息 ORM 模型
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.session import Base


class DrawingSession(Base):
    """绘图会话"""
    __tablename__ = "drawing_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True,
        comment="会话唯一标识（UUID）"
    )
    title: Mapped[str] = mapped_column(
        String(200), nullable=False, default="新建会话",
        comment="会话标题（用于侧边栏展示）"
    )
    drawing_file: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="关联的 AutoCAD 图纸文件路径"
    )
    drawing_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="图纸名称"
    )
    standard_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("drawing_standards.id"), nullable=True,
        comment="当前使用的绘图规范 ID"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="会话是否激活"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        onupdate=datetime.utcnow, server_default=func.now()
    )

    # 关联
    messages: Mapped[list["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<DrawingSession id={self.id} session_id={self.session_id} title={self.title!r}>"


class ChatMessage(Base):
    """对话消息"""
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("drawing_sessions.session_id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False,
        comment="消息角色：user / assistant / system / tool"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False,
        comment="消息内容（Markdown 格式）"
    )
    tool_calls: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="Agent 工具调用记录（JSON 字符串）"
    )
    image_data: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="附带图片的 base64 数据"
    )
    is_streaming: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否为流式输出中"
    )
    token_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="消息 token 数（用于统计）"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow,
        server_default=func.now()
    )

    # 关联
    session: Mapped[DrawingSession] = relationship(
        "DrawingSession", back_populates="messages"
    )

    def __repr__(self) -> str:
        return f"<ChatMessage id={self.id} role={self.role} len={len(self.content)}>"
