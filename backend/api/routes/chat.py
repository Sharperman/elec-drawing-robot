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


@router.delete("/sessions/{session_id}", response_model=ApiResponse)
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """删除指定会话及其所有消息"""
    session = db.query(DrawingSession).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    # 先删消息，再删会话
    db.query(ChatMessage).filter_by(session_id=session_id).delete()
    db.delete(session)
    db.commit()
    return ApiResponse(data={"deleted": session_id})


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
        from knowledge.electrical_standards import electrical_standards
        from feedback.injector import rule_injector
        from agent.draw_agent import get_agent
        from autocad.connection import autocad_connection

        standards_context = await rag_retriever.build_context(request.message)
        _, learned_rules = rule_injector.inject(request.session_id, standards_context)

        # 审查模式：注入电气规范知识库
        mode = getattr(request, 'mode', 'auto')
        if mode == "check":
            review_context = electrical_standards.build_review_context(request.message)
            standards_context = review_context + "\n\n" + standards_context

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
            mode=mode,
        )

        # 审查模式：生成 HTML 报告
        report_path = None
        if mode == "check":
            try:
                review_result = _parse_review_json(response_text)
                if review_result:
                    from autocad.review_report import review_report_generator
                    report_path = review_report_generator.generate(
                        review_result=review_result,
                        dxf_text="",
                        standards_context=standards_context,
                        drawing_path=acad_status.get("drawing_path", ""),
                    )
                    logger.info(f"Review report saved: {report_path}")
            except Exception as report_err:
                logger.warning(f"Failed to generate review report: {report_err}")

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

        result_data = {
            "message": MessageSchema.model_validate(ai_msg).model_dump(),
            "session_id": request.session_id,
        }
        if report_path:
            result_data["report_path"] = report_path

        return ApiResponse(data=result_data)

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
    mode: str = "auto",
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    SSE 流式对话

    客户端通过 EventSource 连接此端点，接收结构化事件流。
    支持三种运行模式: auto(自动), check(审查), draw(绘图)
    数据格式：data: {"type": "...", ...}\n\n
    """
    # 验证 mode
    if mode not in ("auto", "check", "draw"):
        mode = "auto"

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
        """SSE 生成器 — 输出结构化事件"""
        full_response = ""

        try:
            from knowledge.rag_retriever import rag_retriever
            from knowledge.electrical_standards import electrical_standards
            from feedback.injector import rule_injector
            from agent.draw_agent import get_agent
            from autocad.connection import autocad_connection

            # 获取 RAG 规范上下文
            standards_context = await rag_retriever.build_context(message)
            _, learned_rules = rule_injector.inject(session_id, standards_context)

            # 审查模式：注入电气规范知识库
            if mode == "check":
                review_context = electrical_standards.build_review_context(message)
                standards_context = review_context + "\n\n" + standards_context

            acad_status = autocad_connection.get_status()
            acad_connected = acad_status.get("connected", False)
            drawing_name = acad_status.get("drawing_name", "")
            drawing_path = acad_status.get("drawing_path", "")

            agent = get_agent(session_id)

            # ── Draw 模式：先发送确认计划 ──
            if mode == "draw":
                plan = await _analyze_draw_intent(message, standards_context, acad_connected)
                if plan:
                    yield f"data: {json.dumps({'type': 'confirm_required', 'plan': plan}, ensure_ascii=False)}\n\n"

            # 流式生成 — 现在产出 dict 事件
            async for event in agent.chat_stream(
                user_input=message,
                standards_context=standards_context,
                learned_rules=learned_rules,
                acad_connected=acad_connected,
                drawing_name=drawing_name,
                mode=mode,
            ):
                evt_type = event.get("type", "text")
                if evt_type == "text":
                    full_response += event.get("content", "")
                elif evt_type == "done":
                    pass  # 在下面统一处理
                elif evt_type == "error":
                    full_response = event.get("content", "")

                # SSE 格式：所有事件都序列化为 JSON
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

            # 审查模式：生成 HTML 报告
            if mode == "check" and full_response:
                try:
                    # 解析 Agent 输出的审查结果 JSON
                    review_result = _parse_review_json(full_response)
                    if review_result:
                        from autocad.review_report import review_report_generator
                        report_path = review_report_generator.generate(
                            review_result=review_result,
                            dxf_text="",
                            standards_context=standards_context,
                            drawing_path=drawing_path,
                        )
                        logger.info(f"Review report saved: {report_path}")
                        yield f"data: {json.dumps({'type': 'report', 'path': report_path}, ensure_ascii=False)}\n\n"
                except Exception as report_err:
                    logger.warning(f"Failed to generate review report: {report_err}")

            # ── Draw 模式：自动规范校验（P1-05）──
            if mode == "draw" and acad_connected and full_response:
                try:
                    review_result = await _auto_validate_after_draw(
                        session_id=session_id,
                        standards_context=standards_context,
                        drawing_name=drawing_name,
                        drawing_path=drawing_path,
                    )
                    if review_result:
                        yield f"data: {json.dumps({'type': 'auto_review', 'result': review_result}, ensure_ascii=False)}\n\n"
                except Exception as val_err:
                    logger.warning(f"Auto-validate after draw failed: {val_err}")

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

        except Exception as e:
            logger.error(f"Stream error: {e}")
            error_event = {"type": "error", "content": f"抱歉，处理您的请求时出现错误：{str(e)[:200]}"}
            yield f"data: {json.dumps(error_event, ensure_ascii=False)}\n\n"

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


def _parse_review_json(text: str) -> dict | None:
    """
    从 Agent 输出文本中提取审查结果 JSON

    Args:
        text: Agent 完整输出文本

    Returns:
        解析后的审查结果 dict，解析失败返回 None
    """
    import re

    if not text or len(text.strip()) < 10:
        logger.warning("Review text too short to contain JSON")
        return None

    # 尝试直接解析整个文本
    try:
        data = json.loads(text)
        if "checks" in data or "drawing_info" in data:
            logger.info("Parsed review JSON directly from full text")
            return data
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块（贪婪匹配，跨越多行）
    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
    if json_match:
        json_str = json_match.group(1).strip()
        try:
            data = json.loads(json_str)
            if "checks" in data or "drawing_info" in data:
                logger.info(f"Parsed review JSON from code block ({len(json_str)} chars)")
                return data
        except json.JSONDecodeError as e:
            logger.warning(f"JSON code block parse failed: {e}, snippet: {json_str[:200]}...")

    # 尝试提取从 { 开始的最后一个完整 JSON 块（使用括号平衡算法）
    try:
        data = _extract_balanced_json(text)
        if data and ("checks" in data or "drawing_info" in data):
            logger.info("Parsed review JSON via balanced brace extraction")
            return data
    except Exception:
        pass

    # 尝试从不完整 JSON 中恢复（LLM 输出被截断的情况）
    try:
        data = _repair_truncated_json(text)
        if data and ("checks" in data or "drawing_info" in data):
            logger.info("Parsed review JSON via truncation repair")
            return data
    except Exception:
        pass

    # 回退：正则尝试
    matches = list(re.finditer(r'\{[\s\S]*\}', text))
    if matches:
        for m in reversed(matches):
            try:
                data = json.loads(m.group())
                if "checks" in data or "drawing_info" in data:
                    logger.info("Parsed review JSON via regex fallback")
                    return data
            except json.JSONDecodeError:
                continue

    logger.warning(
        f"Could not parse review JSON from agent output. "
        f"Text length: {len(text)}, preview: {text[:300]}...{text[-200:]}"
    )
    return None


def _extract_balanced_json(text: str) -> dict | None:
    """
    使用括号平衡算法从文本中提取完整的 JSON 对象。
    处理 LLM 可能截断或格式不规范的情况。
    """
    import re

    # 找到所有 { 的位置
    for match in re.finditer(r'\{', text):
        start = match.start()
        depth = 0
        in_string = False
        escape_next = False
        end = start

        for i in range(start, len(text)):
            ch = text[i]
            if escape_next:
                escape_next = False
                continue
            if ch == '\\':
                escape_next = True
                continue
            if ch == '"' and not escape_next:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        if depth == 0 and end > start + 10:  # 至少 10 个字符
            candidate = text[start:end]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue

    return None


def _repair_truncated_json(text: str) -> dict | None:
    """
    尝试修复被截断的 JSON。
    当 LLM 输出被 max_tokens 截断时，JSON 可能缺少闭合的 } ] " 等。
    通过括号平衡分析补全截断的 JSON。
    """
    import re

    # 找到 JSON 起始位置（```json 之后或直接 { 开始）
    json_start = -1
    code_block = re.search(r'```(?:json)?\s*\n?', text)
    if code_block:
        json_start = code_block.end()
    else:
        # 找最后一个大的 { 开始
        for m in re.finditer(r'\{', text):
            if text[m.start():].count('"') > 5:  # 至少有一些 JSON 结构
                json_start = m.start()
                # 不 break，取最后一个

    if json_start < 0:
        return None

    json_fragment = text[json_start:]

    # 括号平衡分析：计算需要补多少闭合括号
    depth = 0
    in_string = False
    escape_next = False
    string_delim = None
    open_brackets = []  # stack of open brackets: '{' or '['

    for ch in json_fragment:
        if escape_next:
            escape_next = False
            continue
        if ch == '\\':
            escape_next = True
            continue
        if ch in ('"', "'") and not escape_next:
            if in_string and ch == string_delim:
                in_string = False
            elif not in_string:
                in_string = True
                string_delim = ch
            continue
        if in_string:
            continue
        if ch in ('{', '['):
            depth += 1
            open_brackets.append(ch)
        elif ch in ('}', ']'):
            if open_brackets:
                expected = '{' if ch == '}' else '['
                if open_brackets[-1] == expected:
                    open_brackets.pop()
                    depth -= 1
                else:
                    # 括号不匹配，无法修复
                    return None
            else:
                # 多余的闭合括号
                return None

    # 如果 JSON 片段在字符串内部被截断，补一个引号
    if in_string:
        json_fragment += string_delim
        in_string = False

    # 补全所有未闭合的括号
    closing = ''
    for bracket in reversed(open_brackets):
        closing += '}' if bracket == '{' else ']'

    if not closing and not in_string:
        # 没有需要修复的，可能 JSON 已经完整但不是有效的审查 JSON
        return None

    repaired = json_fragment + closing

    # 也处理最后一个字段值被截断的情况（在字符串中间截断）
    # 如果修复后仍不能解析，尝试去除最后一个不完整的字段
    try:
        data = json.loads(repaired)
        logger.info(f"JSON repaired: added {len(closing)} closing brackets")
        return data
    except json.JSONDecodeError as e:
        # 尝试更激进的修复：去除最后一个不完整的行
        lines = repaired.split('\n')
        for trim in range(1, min(6, len(lines))):
            trimmed = '\n'.join(lines[:-trim])
            # 重新计算需要的闭合括号
            t_depth = 0
            t_brackets = []
            t_in_str = False
            t_esc = False
            t_delim = None
            for ch in trimmed:
                if t_esc:
                    t_esc = False
                    continue
                if ch == '\\':
                    t_esc = True
                    continue
                if ch in ('"', "'") and not t_esc:
                    if t_in_str and ch == t_delim:
                        t_in_str = False
                    elif not t_in_str:
                        t_in_str = True
                        t_delim = ch
                    continue
                if t_in_str:
                    continue
                if ch in ('{', '['):
                    t_brackets.append(ch)
                elif ch in ('}', ']'):
                    if t_brackets:
                        expected = '{' if ch == '}' else '['
                        if t_brackets[-1] == expected:
                            t_brackets.pop()

            if t_in_str:
                trimmed += t_delim

            t_close = ''
            for b in reversed(t_brackets):
                t_close += '}' if b == '{' else ']'

            try:
                data = json.loads(trimmed + t_close)
                logger.info(f"JSON repaired by trimming {trim} lines + {len(t_close)} brackets")
                return data
            except json.JSONDecodeError:
                continue

    return None


async def _analyze_draw_intent(
    user_input: str,
    standards_context: str = "",
    acad_connected: bool = False,
) -> dict | None:
    """
    分析用户的绘图意图，生成操作计划摘要。

    用于 /Draw 模式下的确认预览。

    Args:
        user_input: 用户输入
        standards_context: 规范上下文
        acad_connected: AutoCAD 连接状态

    Returns:
        操作计划 dict，包含 summary 和 operations 列表；分析失败返回 None
    """
    try:
        from config import settings
        from agent.llm_factory import create_primary_llm

        llm = create_primary_llm(
            temperature=0.1,
            max_tokens=800,
        )

        prompt = f"""你是一个电气CAD操作计划分析器。根据用户的绘图指令，生成一个结构化的操作计划JSON。

用户指令：{user_input}
规范上下文：{standards_context[:500] if standards_context else '无'}
AutoCAD连接状态：{'已连接' if acad_connected else '未连接'}

请生成如下JSON（仅输出JSON，不要其他内容）：
{{
  "summary": "一句话概述将要执行的操作（30字内）",
  "operations": [
    {{
      "tool": "工具名（InsertElement/DrawConnection/AddAnnotation/ModifyElement/QueryDrawing之一）",
      "description": "操作描述（中文，40字内）",
      "params": {{}}
    }}
  ]
}}

规则：
- operations 数组最多5项
- tool 必须是: InsertElement, DrawConnection, AddAnnotation, ModifyElement, QueryDrawing
- 如果用户输入不涉及绘图操作（纯咨询），operations 为空数组
- summary 要简洁清晰
- 如果 AutoCAD 未连接，在 summary 中提及"""

        from langchain_core.messages import HumanMessage
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        content = resp.content if hasattr(resp, 'content') else str(resp)

        # 提取 JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            plan = json.loads(json_match.group())
            if isinstance(plan, dict) and 'summary' in plan:
                # 确保 operations 格式正确
                ops = plan.get('operations', [])
                if isinstance(ops, list):
                    valid_ops = []
                    for op in ops[:5]:
                        if isinstance(op, dict):
                            valid_ops.append({
                                'tool': op.get('tool', 'InsertElement'),
                                'description': op.get('description', ''),
                                'params': op.get('params', {}),
                            })
                    plan['operations'] = valid_ops
                return plan

        logger.warning(f"Could not parse draw intent from: {content[:200]}")
        return None

    except Exception as e:
        logger.warning(f"Failed to analyze draw intent: {e}")
        return None


async def _auto_validate_after_draw(
    session_id: str,
    standards_context: str,
    drawing_name: str,
    drawing_path: str,
) -> dict | None:
    """
    P1-05: Draw 模式完成后自动比对规范库，返回不合规项。

    Args:
        session_id: 会话 ID
        standards_context: 规范上下文
        drawing_name: 当前图纸名称
        drawing_path: 图纸路径

    Returns:
        校验结果 dict，包含 issues 列表；失败返回 None
    """
    try:
        from config import settings
        from agent.llm_factory import create_primary_llm
        from autocad.connection import autocad_connection

        # 获取图纸当前状态
        snapshot = autocad_connection.get_snapshot()
        drawing_info = autocad_connection.get_drawing_info() if hasattr(autocad_connection, 'get_drawing_info') else {}
        entity_count = drawing_info.get('entity_count', '未知') if isinstance(drawing_info, dict) else '未知'

        llm = create_primary_llm(
            temperature=0.1,
            max_tokens=1200,
        )

        prompt = f"""你是一个电气图纸规范审查专家。刚完成一次 AutoCAD 绘图操作，请快速检查是否符合规范。

图纸名称：{drawing_name or '未命名'}
图元数量：{entity_count}

规范要求（摘要）：
{standards_context[:1500] if standards_context else '无特定规范要求'}

请生成如下JSON（仅输出JSON，不要其他内容）：
{{
  "summary": "一句话总结校验结果（30字内）",
  "issues": [
    {{
      "severity": "error/warning/info",
      "title": "问题标题（20字内）",
      "description": "问题描述与修改建议（50字内）",
      "rule_id": "关联规则编号（如 STD-001）"
    }}
  ],
  "pass_count": 0,
  "total_checks": 0
}}

规则：
- 如果无问题，issues 为空数组
- severity: error(严重不合规) / warning(建议改进) / info(提示)
- issues 最多5项，只报告确实存在的问题
- pass_count 和 total_checks 为通过和总检查项数"""

        from langchain_core.messages import HumanMessage
        resp = await llm.ainvoke([HumanMessage(content=prompt)])
        content = resp.content if hasattr(resp, 'content') else str(resp)

        # 提取 JSON
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            result = json.loads(json_match.group())
            if isinstance(result, dict) and 'summary' in result:
                result['drawing_name'] = drawing_name
                return result

        logger.warning(f"Could not parse auto-validate result from: {content[:200]}")
        return None

    except Exception as e:
        logger.warning(f"Auto-validate after draw failed: {e}")
        return None
