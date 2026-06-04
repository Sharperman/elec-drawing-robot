"""
/learn 学习模式 API 路由

POST /api/learn/upload      - 上传参考图纸
GET  /api/learn/stream      - SSE 流式学习对话
GET  /api/learn/patterns     - 获取已学模式列表
GET  /api/learn/patterns/{id} - 获取模式详情
POST /api/learn/patterns/{id}/confirm - 确认并保存模式
DEL  /api/learn/patterns/{id} - 删除模式
POST /api/learn/patterns/{id}/apply   - 应用模式到当前绘图
"""
import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from agent.learn_agent import get_learn_agent, clear_learn_agent
from models.drawing_pattern import DrawingPattern
from models.session import get_db
from api.schemas import ApiResponse
from config import settings

router = APIRouter()


# ============================================================
# SSE 流式学习对话
# ============================================================

@router.get("/stream")
async def learn_stream(
    file_id: str = "",
    session_id: str = "",
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    流式学习对话（SSE）

    查询参数：
    - file_id:   上传后返回的文件路径
    - session_id: 会话 ID

    事件类型（与前端 LearnSSEEvent 对齐）：
    - progress:   学习进度（phase + message）
    - screenshot: 截图（screenshot_b64 + description + analysis）
    - pattern:    生成的 DrawingPattern
    - done:       学习完成
    - error:      错误
    """
    async def generate() -> AsyncGenerator[str, None]:
        """在后台线程运行同步 learn_stream，通过 asyncio.Queue 桥接，避免阻塞事件循环。"""
        queue: asyncio.Queue = asyncio.Queue()

        def _run_in_thread():
            """在线程中执行同步 LLM 调用，结果放入队列"""
            try:
                agent = get_learn_agent(session_id)
                if file_id and os.path.exists(file_id):
                    for event in agent.learn_stream(file_id):
                        queue.put_nowait(("data", event))
                else:
                    queue.put_nowait(("data", {"type": "error", "error": "请先上传参考图纸"}))
            except Exception as e:
                logger.error(f"Learn stream error: {e}")
                import traceback
                traceback.print_exc()
                queue.put_nowait(("data", {"type": "error", "error": f"学习过程出错: {str(e)[:200]}"}))
            finally:
                queue.put_nowait(("done", None))

        # 在独立线程中运行，避免阻塞 asyncio 事件循环
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _run_in_thread)

        # 从队列消费，异步 yield
        while True:
            msg_type, payload = await queue.get()
            if msg_type == "done":
                break
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 文件上传
# ============================================================

@router.post("/upload", response_model=ApiResponse)
async def upload_reference_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """
    上传参考图纸文件（DWG / DXF / PDF / PNG / JPG）

    保存后返回文件路径，前端用该路径调用 /learn/stream
    """
    try:
        upload_dir = Path(settings.UPLOAD_DIR) / "learn"
        upload_dir.mkdir(parents=True, exist_ok=True)

        # 生成唯一文件名
        ext = Path(file.filename).suffix or ".dwg"
        unique_name = f"{uuid.uuid4().hex}{ext}"
        save_path = upload_dir / unique_name

        # 保存文件
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        file_path_str = str(save_path)
        logger.info(f"Learn file uploaded: {file_path_str}")

        return ApiResponse(
            data={
                "file_id": file_path_str,    # 前端用 file_id 传回流式端点
                "file_path": file_path_str,  # 兼容旧字段名
                "file_name": file.filename,
                "size": len(content),
            }
        )

    except Exception as e:
        logger.error(f"Learn upload error: {e}")
        return ApiResponse(
            code=500,
            message=f"文件上传失败: {str(e)[:200]}",
        )


# ============================================================
# 模式管理 CRUD
# ============================================================

@router.get("/patterns", response_model=ApiResponse)
async def list_patterns(
    active_only: bool = True,
    db: Session = Depends(get_db),
):
    """获取已学习的图纸模式列表"""
    try:
        query = db.query(DrawingPattern)
        if active_only:
            query = query.filter_by(is_active=True)
        patterns = query.order_by(DrawingPattern.created_at.desc()).all()
        return ApiResponse(
            data=[p.to_dict() for p in patterns]
        )
    except Exception as e:
        logger.error(f"List patterns error: {e}")
        return ApiResponse(code=500, message=str(e))


@router.get("/patterns/{pattern_id}", response_model=ApiResponse)
async def get_pattern(
    pattern_id: int,
    db: Session = Depends(get_db),
):
    """获取单个模式详情"""
    dp = db.query(DrawingPattern).filter_by(id=pattern_id).first()
    if not dp:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return ApiResponse(data=dp.to_dict())


@router.post("/patterns/{pattern_id}/confirm", response_model=ApiResponse)
async def confirm_pattern(
    pattern_id: int,
    overrides: Optional[dict] = None,
    user_notes: Optional[str] = None,
    session_id: str = "",
    confirmed: bool = True,
    db: Session = Depends(get_db),
):
    """
    确认并保存 Pattern

    - 如果 pattern_id > 0 且存在，更新现有记录
    - 如果 pattern_id == 0 或不存在，从 LearnAgent 取数据创建新记录
    """
    try:
        if pattern_id > 0:
            dp = db.query(DrawingPattern).filter_by(id=pattern_id).first()
        else:
            dp = None

        if dp is None:
            # 从 LearnAgent 获取临时 pattern 数据
            pattern_data = None
            if session_id:
                try:
                    from agent.learn_agent import _learn_agents
                    agent = _learn_agents.get(session_id)
                    if agent and agent._pattern:
                        pattern_data = agent._pattern
                except Exception:
                    pass

            if not pattern_data and overrides:
                pattern_data = overrides

            if not pattern_data:
                return ApiResponse(code=400, message="没有可保存的 Pattern 数据")

            dp = DrawingPattern()
            db.add(dp)
            # 填充数据
            dp.name = pattern_data.get("name", "未命名模式")
            dp.description = pattern_data.get("description", "")
            dp.source_file = pattern_data.get("source_file", "")
            dp.source_type = pattern_data.get("source_type", "dwg")
            dp.update_from_dict(pattern_data)

        # 如果传了 overrides，合并覆盖
        if overrides and isinstance(overrides, dict):
            dp.update_from_dict(overrides)

        if user_notes:
            dp.description = (dp.description or "") + f"\n\n## 用户补充\n{user_notes}"

        dp.is_active = True
        db.commit()
        db.refresh(dp)

        # 清除 agent 实例
        if session_id:
            clear_learn_agent(session_id)

        return ApiResponse(
            data={"pattern_id": dp.id, "message": f"图纸模式已保存（ID: {dp.id}）"}
        )

    except Exception as e:
        logger.error(f"Confirm pattern error: {e}")
        return ApiResponse(code=500, message=str(e))


@router.delete("/patterns/{pattern_id}", response_model=ApiResponse)
async def delete_pattern(
    pattern_id: int,
    db: Session = Depends(get_db),
):
    """删除图纸模式（软删除，设置 is_active=False）"""
    dp = db.query(DrawingPattern).filter_by(id=pattern_id).first()
    if not dp:
        raise HTTPException(status_code=404, detail="Pattern not found")
    dp.is_active = False
    db.commit()
    return ApiResponse(data={"deleted": pattern_id})


# ============================================================
# 应用模式到当前绘图
# ============================================================

@router.post("/patterns/{pattern_id}/apply", response_model=ApiResponse)
async def apply_pattern(
    pattern_id: int,
    session_id: str = "",
    db: Session = Depends(get_db),
):
    """
    将学习到的模式应用到当前绘图会话

    将 Pattern 中的 layout_rules / devices / connection_patterns
    注入到 CanvasState 或 Agent 的上下文中，
    使后续绘图参考该模式。
    """
    dp = db.query(DrawingPattern).filter_by(id=pattern_id, is_active=True).first()
    if not dp:
        raise HTTPException(status_code=404, detail="Pattern not found")

    try:
        # 增加使用计数
        dp.usage_count = (dp.usage_count or 0) + 1
        db.commit()

        # 将 pattern 注入到会话上下文（如果 context_manager 可用）
        try:
            from agent.context_manager import get_context
            ctx = get_context(session_id)
            if ctx and hasattr(ctx, 'set_learned_pattern'):
                ctx.set_learned_pattern(dp.to_dict())
                logger.info(f"Pattern {pattern_id} applied to session {session_id} via context_manager")
        except ImportError:
            logger.warning("context_manager not available, pattern saved but not injected to session")
        except Exception as ctx_err:
            logger.warning(f"Failed to inject pattern to context: {ctx_err}")

        return ApiResponse(
            data={
                "pattern_id": pattern_id,
                "pattern_name": dp.name,
                "message": f"已应用模式「{dp.name}」到当前会话",
            }
        )

    except Exception as e:
        logger.error(f"Apply pattern error: {e}")
        return ApiResponse(code=500, message=str(e))
