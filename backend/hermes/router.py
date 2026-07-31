"""
Hermes API 路由 v2 — 完整 Skill 管理
POST /api/hermes/toggle           — 开关 Computer Use
POST /api/hermes/interrupt        — 中断当前操作
GET  /api/hermes/status           — 获取 Hermes 状态
GET  /api/hermes/skills           — 列出所有 Skill（支持分类筛选）
GET  /api/hermes/skills/{id}      — 获取单个 Skill 详情
POST /api/hermes/skills/{id}/execute  — 执行 Skill（SSE 流）
POST /api/hermes/skills/{id}/enable|disable  — 启用/禁用
DELETE /api/hermes/skills/{id}    — 删除 Skill
GET  /api/hermes/skills/match     — 匹配 Skill（斜杠命令）
POST /api/hermes/skills/autocreate  — 自动创建 Skill
POST /api/hermes/parse-command    — 解析用户命令
"""
from __future__ import annotations

import json
from typing import Any

from api.schemas import ApiResponse
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from loguru import logger
from pydantic import BaseModel, Field

from hermes import (
    _ensure_default_skills,
    _registry,
    get_hermes_tools,
    hermes_state,
)
from hermes.auto_creator import SkillAutoCreator
from hermes.models.skill import (
    HermesSkill,
    SkillCategory,
    SkillStatus,
)
from hermes.skill_executor import SkillExecutor
from hermes.skill_registry import SkillRegistry

router = APIRouter()

# ─── Request Models ────────────────────────────────

class ToggleRequest(BaseModel):
    enabled: bool = Field(..., description="true=开启, false=关闭")


class ExecuteRequest(BaseModel):
    inputs: dict[str, Any] = Field(
        default_factory=dict, description="输入参数"
    )
    stream: bool = Field(default=True, description="是否 SSE 流式返回")


class AutoCreateRequest(BaseModel):
    task_description: str = Field(..., description="任务描述")
    execution_trace: list[dict[str, Any]] = Field(
        ..., description="执行轨迹"
    )
    auto_confirm: bool = Field(
        default=False, description="是否自动确认"
    )


class ParseCommandRequest(BaseModel):
    text: str = Field(..., description="用户输入的文本")


class SkillUpdateRequest(BaseModel):
    status: str | None = Field(default=None, description="active|disabled")


# ─── 全局单例 ──────────────────────────────────

_skill_executor: SkillExecutor | None = None
_skill_registry: SkillRegistry | None = None
_auto_creator: SkillAutoCreator | None = None


def _get_registry() -> SkillRegistry:
    """获取或创建全局 SkillRegistry"""
    global _skill_registry
    if _skill_registry is None:
        from pathlib import Path
        reg_dir = Path(__file__).parent / "skills"
        _skill_registry = SkillRegistry(str(reg_dir))
        # 加载内置 Skills
        _ensure_default_skills()
        for sk in _registry:
            hs = _hermes_skill_from_builtin(sk)
            if hs:
                _skill_registry.register_internal(hs)
        # 加载外部 Skills
        _skill_registry.load_external_skills()
        logger.info(f"SkillRegistry 初始化完成: {_skill_registry.count()}")
    return _skill_registry


def _get_executor() -> SkillExecutor:
    """获取或创建全局 SkillExecutor"""
    global _skill_executor
    if _skill_executor is None:
        _skill_executor = SkillExecutor()
        # 注册工具 — 从 Hermes 内置工具映射
        for tool in get_hermes_tools():
            _skill_executor.register_tool(tool.name, tool)
        # AutoCAD 工具在 DrawAgent 中注册，Hermes 只管理桌面工具
        logger.info(f"SkillExecutor 初始化完成: {len(_skill_executor.get_tool_names())} 个工具")
    return _skill_executor


def _get_creator() -> SkillAutoCreator:
    """获取或创建全局 AutoCreator"""
    global _auto_creator
    if _auto_creator is None:
        _auto_creator = SkillAutoCreator()
    return _auto_creator


def _hermes_skill_from_builtin(
    builtin_skill: Any
) -> HermesSkill | None:
    """将 Hermes 内置 Skill 转为 HermesSkill 对象"""
    try:
        from hermes.models.skill import (
            SkillExecutionConfig,
            SkillInputSchema,
            SkillMetadata,
            SkillStep,
        )

        # 内置 Skill 没有(steps)属性，创建单步骤引用自身工具名
        tool_name = getattr(builtin_skill, "name", "")
        desc = getattr(builtin_skill, "description", "")
        steps = [SkillStep(
            tool=tool_name,
            params={},
            description=f"执行内置工具: {tool_name}",
        )]

        return HermesSkill(
            skill_id=tool_name,
            metadata=SkillMetadata(
                name=tool_name,
                description=desc,
                author="builtin",
            ),
            category=SkillCategory.INTERNAL,
            execution=SkillExecutionConfig(
                type="python", entry="builtin", steps=steps
            ),
            inputs=SkillInputSchema(),
        )
    except Exception as e:
        logger.warning(f"内置 Skill 转换失败: {e}")
        return None


# ─── API 实现 ─────────────────────────────────

@router.post("/toggle", response_model=ApiResponse)
def toggle_hermes(body: ToggleRequest) -> ApiResponse:
    """开启/关闭 Computer Use（Hermes 工具注入）"""
    prev = hermes_state.enabled
    hermes_state.enabled = body.enabled

    if body.enabled and not prev:
        logger.info("Hermes (Computer Use) 已开启")
        hermes_state.set_status("Hermes 已就绪")
    elif not body.enabled and prev:
        logger.info("Hermes (Computer Use) 已关闭")
        if hermes_state.running:
            hermes_state.interrupt()

    return ApiResponse(data=hermes_state.status_dict())


@router.post("/interrupt", response_model=ApiResponse)
def interrupt_hermes() -> ApiResponse:
    """中断当前 Hermes 操作"""
    hermes_state.interrupt()
    return ApiResponse(data={"interrupted": True})


@router.get("/status", response_model=ApiResponse)
def hermes_status() -> ApiResponse:
    """获取 Hermes 状态"""
    data = hermes_state.status_dict()
    registry = _get_registry()
    data["skills"] = registry.count()
    return ApiResponse(data=data)


@router.get("/skills", response_model=ApiResponse)
def list_skills(
    category: str | None = Query(None, description="筛选分类"),
) -> ApiResponse:
    """列出所有 Hermes Skills"""
    registry = _get_registry()

    if category:
        try:
            cat_enum = SkillCategory(category)
            skills = registry.get_by_category(cat_enum)
        except ValueError:
            skills = registry.get_all()
    else:
        skills = registry.get_all()

    return ApiResponse(data={
        "skills": [s.to_dict() for s in skills],
        "count": len(skills),
        "categories": registry.count(),
    })


@router.get("/skills/match", response_model=ApiResponse)
def match_skills(
    q: str = Query(..., description="查询文本"),
    top_k: int = Query(5, description="返回数量"),
) -> ApiResponse:
    """根据文本匹配最佳 Skill（必须在 /skills/{skill_id} 之前定义）"""
    registry = _get_registry()
    matches = registry.find_matching(q, top_k)
    return ApiResponse(data={
        "matches": [
            {
                "skill_id": m.skill.skill_id,
                "name": m.skill.metadata.name,
                "description": m.skill.metadata.description,
                "match_type": m.match_type,
                "confidence": m.confidence,
            }
            for m in matches
        ],
        "count": len(matches),
    })


@router.get("/skills/{skill_id}", response_model=ApiResponse)
def get_skill(skill_id: str) -> ApiResponse:
    """获取单个 Skill 详情"""
    registry = _get_registry()
    skill = registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")
    return ApiResponse(data=skill.to_dict())


@router.post("/skills/{skill_id}/execute")
async def execute_skill(
    skill_id: str,
    body: ExecuteRequest | None = None,
):
    """执行 Skill（流式 SSE）"""
    registry = _get_registry()
    skill = registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")

    inputs = body.inputs if body else {}
    stream_mode = body.stream if body else True

    executor = _get_executor()

    if not stream_mode:
        # 非流式执行
        result = await executor.execute(skill, inputs)
        # 更新统计
        skill.use_count += 1
        if result.success:
            skill.success_count += 1
        return ApiResponse(data=result.model_dump())

    # 流式 SSE
    async def event_stream():
        logs_buffer = []
        yield f"data: {json.dumps({'event': 'start', 'skill_id': skill_id})}\n\n"

        async def step_callback(step_idx: int, total: int, status: str, result: Any = None):
            nonlocal logs_buffer
            event_data = {
                "event": "step",
                "step": step_idx,
                "total": total,
                "status": status,
            }
            if result:
                event_data["result"] = result
            yield f"data: {json.dumps(event_data)}\n\n"

        # 自定义执行
        steps = skill.execution.steps

        for step_idx, step in enumerate(steps):
            # 中断检查
            if hermes_state.interrupt_requested:
                yield f"data: {json.dumps({'event': 'interrupted', 'step': step_idx + 1})}\n\n"
                return

            params = executor._resolve_params(step.params, inputs)
            yield f"data: {json.dumps({'event': 'step_start', 'step': step_idx + 1, 'total': len(steps), 'tool': step.tool, 'params': params})}\n\n"

            try:
                success, message = await executor._execute_step(step, params, step_idx)
                result = {"success": success, "message": message[:500]}
                yield f"data: {json.dumps({'event': 'step_end', 'step': step_idx + 1, 'result': result})}\n\n"

                if not success:
                    raise Exception(message)
            except Exception as e:
                yield f"data: {json.dumps({'event': 'error', 'step': step_idx + 1, 'message': str(e)})}\n\n"
                return

        yield f"data: {json.dumps({'event': 'complete', 'success': True})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/skills/{skill_id}/toggle-status", response_model=ApiResponse)
def toggle_skill_status(
    skill_id: str,
    body: SkillUpdateRequest,
) -> ApiResponse:
    """启用/禁用 Skill"""
    registry = _get_registry()
    skill = registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")

    if body.status == "disabled":
        skill.status = SkillStatus.DISABLED
    elif body.status == "active":
        skill.status = SkillStatus.ACTIVE

    return ApiResponse(data={
        "skill_id": skill_id,
        "status": skill.status.value,
    })


@router.delete("/skills/{skill_id}", response_model=ApiResponse)
def delete_skill(skill_id: str) -> ApiResponse:
    """删除 Skill"""
    registry = _get_registry()
    skill = registry.get(skill_id)
    if not skill:
        raise HTTPException(status_code=404, detail=f"Skill '{skill_id}' 不存在")

    if skill.category == SkillCategory.INTERNAL:
        raise HTTPException(status_code=400, detail="内置 Skill 不能删除")

    if skill.category == SkillCategory.AUTOGEN:
        registry.delete_autogen_skill(skill_id)

    registry.unregister(skill_id)
    return ApiResponse(data={"skill_id": skill_id, "deleted": True})


@router.post("/skills/autocreate", response_model=ApiResponse)
async def auto_create_skill(body: AutoCreateRequest) -> ApiResponse:
    """自动创建 Skill"""
    creator = _get_creator()
    result = await creator.create_from_execution(
        task_description=body.task_description,
        execution_trace=body.execution_trace,
        user_confirmation=body.auto_confirm,
    )

    if not result.skill:
        return ApiResponse(
            code=400,
            message=result.message,
        )

    registry = _get_registry()

    if not result.requires_confirmation:
        # 自动确认，直接注册
        registry.register_autogen(result.skill)
        registry.save_autogen_skill(result.skill)
        return ApiResponse(data={
            **result.to_dict(),
            "registered": True,
        })
    else:
        return ApiResponse(data={
            **result.to_dict(),
            "registered": False,
        })


@router.post("/skills/autocreate/confirm", response_model=ApiResponse)
def confirm_auto_skill(
    body: dict[str, Any],
) -> ApiResponse:
    """确认保存自动创建的 Skill"""
    skill_id = body.get("skill_id")
    skill_dict = body.get("skill")

    if not skill_dict and not skill_id:
        raise HTTPException(status_code=400, detail="需要 skill_id 或 skill 数据")

    if skill_id:
        # 从已创建但未注册的缓存中查找
        # 简化处理：直接用提供的 skill 数据
        pass

    if skill_dict:
        skill = HermesSkill.from_dict(skill_dict)
        registry = _get_registry()
        registry.register_autogen(skill)
        registry.save_autogen_skill(skill)
        return ApiResponse(data={
            "skill_id": skill.skill_id,
            "registered": True,
        })

    return ApiResponse(code=400, message="无法确认")


@router.post("/parse-command", response_model=ApiResponse)
def parse_command(body: ParseCommandRequest) -> ApiResponse:
    """解析斜杠命令"""
    text = body.text.strip()

    # 斜杠命令格式: /command arg1 arg2
    if text.startswith("/"):
        parts = text[1:].split(None, 1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        # 匹配斜杠命令
        registry = _get_registry()
        slash_cmds = registry.to_slash_commands()

        cmd_key = f"/{cmd}"
        cmd_info = slash_cmds.get(cmd_key)

        if cmd_info:
            # 尝试解析参数
            parsed = _parse_args_to_inputs(args, cmd_info)
            return ApiResponse(data={
                "is_command": True,
                "command": cmd_key,
                "skill_id": cmd_info["skill_id"],
                "raw_args": args,
                "parsed_inputs": parsed,
                "description": cmd_info["description"],
            })

        return ApiResponse(data={
            "is_command": True,
            "command": cmd_key,
            "skill_id": None,
            "raw_args": args,
            "parsed_inputs": {},
            "description": f"未知命令: {cmd_key}",
            "suggestions": [
                {"command": k, "description": v["description"]}
                for k, v in slash_cmds.items()
            ],
        })

    # 非斜杠命令 — 尝试匹配 Skill 触发词
    registry = _get_registry()
    matches = registry.find_matching(text, top_k=3)

    if matches and matches[0].confidence >= 0.8:
        return ApiResponse(data={
            "is_command": False,
            "matched_skill": matches[0].skill.skill_id,
            "confidence": matches[0].confidence,
            "description": matches[0].skill.metadata.description,
        })

    return ApiResponse(data={
        "is_command": False,
        "matched_skill": None,
        "confidence": 0.0,
        "description": None,
    })


def _parse_args_to_inputs(
    args: str, cmd_info: dict[str, Any]
) -> dict[str, str]:
    """简单参数解析"""
    if not args:
        return {}
    return {"text": args}
