"""
录制和回放 API 路由
POST   /api/recording/start      — 开始录制
POST   /api/recording/stop       — 停止录制
GET    /api/recording/sessions   — 录制会话列表
GET    /api/recording/sessions/{id} — 会话详情 + 步骤列表
POST   /api/recording/sessions/{id}/analyze — 手动触发分析
POST   /api/recording/sessions/{id}/delete — 删除录制
"""
import datetime
import json
import uuid

from api.schemas import ApiResponse
from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from models.operation_session import OperationSession, OperationStep
from models.session import get_db
from sqlalchemy import desc
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/start", response_model=ApiResponse)
def start_recording(
    session_name: str = Query(""),
    cad_file: str = Query(""),
    fps: int = Query(5, ge=1, le=30),
    db: Session = Depends(get_db),
):
    """开始录制"""
    from agent.background_recorder import background_recorder
    from desktop.video_recorder import video_recorder

    session_id_str = uuid.uuid4().hex[:12]

    # 创建数据库记录
    s = OperationSession(
        session_name=session_name or f"录制_{session_id_str[:6]}",
        cad_file=cad_file,
        status="recording",
        fps=fps,
    )
    db.add(s)
    db.commit()
    db.refresh(s)

    # 启动录制器
    video_recorder.fps = fps
    video_recorder.start(session_id_str)

    # 启动 COM 采样
    background_recorder.start(s.id, session_name, cad_file)

    return ApiResponse(data={"session_id": s.id, "recording_id": session_id_str})


@router.post("/stop", response_model=ApiResponse)
def stop_recording(db: Session = Depends(get_db)):
    """停止录制"""
    from agent.background_recorder import background_recorder
    from desktop.video_recorder import video_recorder

    # 停止录制引擎
    video_info = video_recorder.stop()
    steps = background_recorder.stop()

    # 查找最近 recording 状态的 session
    session = db.query(OperationSession).filter_by(status="recording").order_by(
        desc(OperationSession.started_at)).first()
    if not session:
        return ApiResponse(code=400, message="没有正在录制的会话")

    # 更新会话
    session.ended_at = datetime.datetime.utcnow()
    session.duration_seconds = video_info.get("duration_seconds", 0)
    session.video_segments = json.dumps(video_info.get("segments", []), ensure_ascii=False)
    session.total_frames = video_info.get("total_frames", 0)
    session.resolution = video_info.get("resolution", "1920x1080")
    session.status = "stopped"
    session.step_count = len(steps)

    # 批量写入步骤
    if steps:
        from models.operation_session import OperationStep
        for i, step in enumerate(steps):
            op_step = OperationStep(
                session_id=session.id,
                seq=i,
                timestamp=step.get("timestamp", 0),
                step_type=step.get("step_type", "unknown"),
                entities_json=json.dumps(step.get("entities", []), ensure_ascii=False),
                description=step.get("description", ""),
            )
            db.add(op_step)

    # 计算坐标映射
    try:
        from autocad.zoom_control import get_zoom_controller
        zc = get_zoom_controller()
        ext = zc.get_view_extents()
        if ext:
            session.coord_map = json.dumps({"view_extents": ext}, ensure_ascii=False)
    except Exception:
        pass

    db.commit()

    return ApiResponse(data={
        "session_id": session.id,
        "duration_seconds": session.duration_seconds,
        "step_count": session.step_count,
    })


@router.get("/sessions", response_model=ApiResponse)
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """录制会话列表"""
    q = db.query(OperationSession).order_by(desc(OperationSession.started_at))
    total = q.count()
    sessions = q.offset((page - 1) * page_size).limit(page_size).all()
    return ApiResponse(data={"items": [s.to_dict() for s in sessions], "total": total, "page": page})


@router.get("/sessions/{session_id}", response_model=ApiResponse)
def get_session_detail(session_id: int, db: Session = Depends(get_db)):
    """会话详情 + 步骤列表"""
    session = db.query(OperationSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="录制不存在")

    steps = db.query(OperationStep).filter_by(session_id=session_id).order_by(OperationStep.seq).all()

    return ApiResponse(data={
        "session": session.to_dict(),
        "steps": [s.to_dict() for s in steps],
    })


@router.post("/sessions/{session_id}/analyze", response_model=ApiResponse)
def analyze_session(session_id: int, db: Session = Depends(get_db)):
    """手动触发分析：LLM 分析录制内容 → 生成 Workflow Pattern"""
    session = db.query(OperationSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="录制不存在")
    if session.status not in ("stopped", "done"):
        return ApiResponse(code=400, message="录制未完成，请先停止录制")

    session.status = "analyzing"
    db.commit()

    # 在后台线程中执行分析
    import threading

    def _analyze():
        db2 = None
        try:
            from agent.workflow_analyzer import workflow_analyzer
            result = workflow_analyzer.analyze(session_id)
            from models.session import get_session_local
            db2 = get_session_local()()
            s = db2.query(OperationSession).filter_by(id=session_id).first()
            if s:
                s.status = "done"
                s.pattern_id = result.get("pattern_id")
                db2.commit()
        except Exception as e:
            logger.error(f"分析失败: {e}")
            if db2:
                s = db2.query(OperationSession).filter_by(id=session_id).first()
                if s:
                    s.status = "error"
                    db2.commit()
        finally:
            if db2:
                db2.close()

    threading.Thread(target=_analyze, daemon=True).start()
    return ApiResponse(data={"session_id": session_id, "status": "analyzing"})


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
def delete_session(session_id: int, db: Session = Depends(get_db)):
    """删除录制（含视频文件）"""
    session = db.query(OperationSession).filter_by(id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="录制不存在")

    # 删除视频文件
    if session.video_segments:
        try:
            segs = json.loads(session.video_segments)
            from desktop.video_recorder import video_recorder
            for seg in segs:
                # segment文件名不含session目录，需拼接
                import os
                for root, _, files in os.walk(str(video_recorder.output_dir)):
                    if seg in files:
                        os.unlink(os.path.join(root, seg))
        except Exception:
            pass

    db.query(OperationStep).filter_by(session_id=session_id).delete()
    db.delete(session)
    db.commit()
    return ApiResponse(data={"deleted": session_id})
