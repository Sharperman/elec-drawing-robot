"""
Chat 路由
POST /api/chat        - 非流式对话
GET  /api/chat/stream - SSE 流式对话
POST /api/chat/confirm - 确认执行计划
"""
import asyncio
import json
import uuid
from datetime import datetime
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from loguru import logger
from sqlalchemy.orm import Session

from api.schemas import (
    ApiResponse, ChatRequest, ChatConfirmRequest,
    MessageSchema, CreateSessionRequest, SessionSchema,
)
from models.session import get_db
from models.drawing_session import DrawingSession, ChatMessage
from utils.error_codes import ErrorCode, get_error_message

router = APIRouter()


# ============================================================
# 会话管理
# ============================================================

@router.post("/sessions", response_model=ApiResponse)
async def create_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """创建新绘图会话"""
    session = DrawingSession(
        session_id=str(uuid.uuid4()),
        title=request.title,
        drawing_file=request.drawing_file,
        standard_id=request.standard_id,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return ApiResponse(
        data=SessionSchema.model_validate(session).model_dump()
    )


@router.get("/sessions", response_model=ApiResponse)
async def list_sessions(db: Session = Depends(get_db)) -> ApiResponse:
    """获取所有会话列表"""
    sessions = db.query(DrawingSession).order_by(DrawingSession.updated_at.desc()).all()
    return ApiResponse(
        data=[SessionSchema.model_validate(s).model_dump() for s in sessions]
    )


@router.get("/sessions/{session_id}/messages", response_model=ApiResponse)
async def get_messages(
    session_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """获取会话消息历史"""
    session = db.query(DrawingSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(ChatMessage)
        .filter_by(session_id=session_id)
        .order_by(ChatMessage.created_at)
        .all()
    )
    return ApiResponse(
        data=[MessageSchema.model_validate(m).model_dump() for m in messages]
    )


# ============================================================
# 对话端点
# ============================================================

@router.post("", response_model=ApiResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    非流式对话（完整响应）

    适用于：测试、简单查询
    """
    # 确保会话存在
    session = db.query(DrawingSession).filter_by(session_id=request.session_id).first()
    if not session:
        raise HTTPException(
            status_code=404,
            detail=get_error_message(ErrorCode.SESSION_NOT_FOUND),
        )

    # 保存用户消息
    user_msg = ChatMessage(
        session_id=request.session_id,
        role="user",
        content=request.message,
        image_data=request.image_data,
    )
    db.add(user_msg)
    db.commit()

    try:
        # 获取 RAG 规范上下文
        from knowledge.rag_retriever import rag_retriever
        from feedback.injector import rule_injector
        from agent.draw_agent import get_agent
        from autocad.connection import autocad_connection

        standards_context = await rag_retriever.build_context(request.message)
        _, learned_rules = rule_injector.inject(request.session_id, standards_context)

        # 获取 AutoCAD 连接状态
        acad_status = autocad_connection.get_status()
        acad_connected = acad_status.get("connected", False)
        drawing_name = acad_status.get("drawing_name", "")

        # 调用 Agent
        agent = get_agent(request.session_id)
        response_text = await agent.chat(
            user_input=request.message,
            image_data=request.image_data,
            standards_context=standards_context,
            learned_rules=learned_rules,
            acad_connected=acad_connected,
            drawing_name=drawing_name,
        )

        # 保存 Assistant 回复
        ai_msg = ChatMessage(
            session_id=request.session_id,
            role="assistant",
            content=response_text,
        )
        db.add(ai_msg)
        # 更新会话时间
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(ai_msg)

        return ApiResponse(
            data={
                "message": MessageSchema.model_validate(ai_msg).model_dump(),
                "session_id": request.session_id,
            }
        )

    except Exception as e:
        logger.error(f"Chat error: {e}")
        return ApiResponse(
            code=ErrorCode.AGENT_TOOL_ERROR,
            message=get_error_message(ErrorCode.AGENT_TOOL_ERROR),
            data={"error": str(e)},
        )


@router.get("/stream")
async def chat_stream(
    session_id: str,
    message: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    SSE 流式对话

    客户端通过 EventSource 连接此端点，接收 token 级别的流式响应。
    数据格式：data: <token>\n\n
    """
    # 验证会话
    session = db.query(DrawingSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # 保存用户消息
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=message,
    )
    db.add(user_msg)
    db.commit()

    async def generate() -> AsyncIterator[str]:
        """SSE 生成器"""
        full_response = ""

        try:
            from knowledge.rag_retriever import rag_retriever
            from feedback.injector import rule_injector
            from agent.draw_agent import get_agent
            from autocad.connection import autocad_connection

            standards_context = await rag_retriever.build_context(message)
            _, learned_rules = rule_injector.inject(session_id, standards_context)

            acad_status = autocad_connection.get_status()
            acad_connected = acad_status.get("connected", False)
            drawing_name = acad_status.get("drawing_name", "")

            agent = get_agent(session_id)

            # 流式生成
            async for token in agent.chat_stream(
                user_input=message,
                standards_context=standards_context,
                learned_rules=learned_rules,
                acad_connected=acad_connected,
                drawing_name=drawing_name,
            ):
                full_response += token
                # SSE 格式
                yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"

            # 保存完整响应到数据库
            new_db = None
            try:
                from models.session import get_session_local
                new_db = get_session_local()()
                ai_msg = ChatMessage(
                    session_id=session_id,
                    role="assistant",
                    content=full_response,
                )
                new_db.add(ai_msg)
                new_db.commit()
            except Exception as db_err:
                logger.warning(f"Failed to save streamed message: {db_err}")
            finally:
                if new_db:
                    new_db.close()

            # 发送完成信号
            yield f"data: {json.dumps({'token': '', 'done': True, 'full': full_response})}\n\n"

        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_msg = f"抱歉，处理您的请求时出现错误：{str(e)[:200]}"
            yield f"data: {json.dumps({'token': error_msg, 'done': True, 'error': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/confirm", response_model=ApiResponse)
async def confirm_plan(
    request: ChatConfirmRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    确认或取消 Agent 的操作计划

    当 Agent 提出操作计划需要用户确认时使用。
    """
    from agent.context_manager import get_context

    context = get_context(request.session_id)
    pending = context.get_pending_plan()

    if not pending:
        return ApiResponse(
            code=ErrorCode.NOT_FOUND,
            message="没有待确认的操作计划",
        )

    if request.confirm:
        context.clear_pending_plan()
        return ApiResponse(data={"message": "操作计划已确认，开始执行"})
    else:
        context.clear_pending_plan()
        return ApiResponse(data={"message": "操作计划已取消"})
