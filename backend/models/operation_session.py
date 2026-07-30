"""
OperationSession + OperationStep 数据模型
录制 CAD 操作会话和步骤，用于后台学习和回放。
"""
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column, Integer, String, Text, Float, DateTime, ForeignKey, Index,
)
from sqlalchemy.sql import func

from models.session import Base


class OperationSession(Base):
    """录制会话表"""
    __tablename__ = "operation_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_name = Column(String(200), comment="录制名称")
    cad_file = Column(String(500), comment="关联的 DWG 文件路径")
    started_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, default=0, comment="录制时长(秒)")
    video_segments = Column(Text, comment="JSON: 视频文件列表")
    total_frames = Column(Integer, default=0)
    step_count = Column(Integer, default=0)
    pattern_id = Column(Integer, nullable=True, comment="分析后关联的 DrawingPattern ID")
    status = Column(String(20), default="recording", comment="recording/stopped/analyzing/done/error")
    fps = Column(Integer, default=5)
    resolution = Column(String(30))
    coord_map = Column(Text, comment="JSON: CAD坐标→屏幕像素映射")
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_opsess_status", "status"),
        Index("idx_opsess_created", "created_at"),
    )

    def to_dict(self) -> dict:
        import json
        segments = []
        if self.video_segments:
            try:
                segments = json.loads(self.video_segments)
            except Exception:
                pass
        return {
            "id": self.id,
            "session_name": self.session_name,
            "cad_file": self.cad_file,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_seconds": self.duration_seconds,
            "video_segments": segments,
            "total_frames": self.total_frames,
            "step_count": self.step_count,
            "pattern_id": self.pattern_id,
            "status": self.status,
            "fps": self.fps,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class OperationStep(Base):
    """录制步骤表"""
    __tablename__ = "operation_steps"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("operation_sessions.id", ondelete="CASCADE"), nullable=False)
    seq = Column(Integer, comment="步骤序号")
    timestamp = Column(Float, comment="相对录制开始秒数")
    frame_number = Column(Integer, default=0, comment="对应视频帧号")
    step_type = Column(String(20), comment="add/delete/modify/command/idle")
    entities_json = Column(Text, comment="JSON: 涉及的实体列表")
    description = Column(Text, comment="LLM 自动生成的描述")
    created_at = Column(DateTime, default=func.now())

    __table_args__ = (
        Index("idx_opstep_session", "session_id"),
        Index("idx_opstep_seq", "session_id", "seq"),
    )

    def to_dict(self) -> dict:
        import json
        entities = []
        if self.entities_json:
            try:
                entities = json.loads(self.entities_json)
            except Exception:
                pass
        return {
            "id": self.id,
            "session_id": self.session_id,
            "seq": self.seq,
            "timestamp": self.timestamp,
            "frame_number": self.frame_number,
            "step_type": self.step_type,
            "entities": entities,
            "description": self.description,
        }
