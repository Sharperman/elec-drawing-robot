"""
Skill Executor — Skill 执行引擎
按步骤执行 Skill，支持参数模板解析、中断检查、超时控制
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from loguru import logger

from hermes.models.skill import (
    ExecutionResult,
    HermesSkill,
    SkillStep,
)


class SkillExecutor:
    """
    Skill 执行引擎

    职责：
    1. 解析参数模板（${inputs.x} → 实际值）
    2. 按步骤调用对应工具
    3. 支持中断检查
    4. 收集执行日志
    """

    # 参数模板匹配正则: ${inputs.name} 或 ${inputs.nested.key}
    TEMPLATE_PATTERN = re.compile(r"\$\{inputs\.([^}]+)\}")

    def __init__(self):
        self._tool_registry: dict[str, Any] = {}

    def register_tool(self, name: str, tool_fn: Any) -> None:
        """注册可调用的工具"""
        self._tool_registry[name] = tool_fn

    def register_tools(self, tools: dict[str, Any]) -> None:
        """批量注册工具"""
        self._tool_registry.update(tools)

    def get_tool_names(self) -> list[str]:
        """获取已注册的工具名称列表"""
        return list(self._tool_registry.keys())

    # ─── 核心 ────────────────────────────────────────────

    async def execute(
        self,
        skill: HermesSkill,
        inputs: dict[str, Any],
        interrupt_check: callable | None = None,
    ) -> ExecutionResult:
        """
        执行 Skill

        Args:
            skill: 要执行的 Skill
            inputs: 用户输入参数
            interrupt_check: 中断检查回调，返回 True 表示应中断

        Returns:
            ExecutionResult: 执行结果
        """
        start_time = time.monotonic()
        logs: list[str] = []
        outputs: list[dict[str, Any]] = []

        logger.info(f"开始执行 Skill: {skill.skill_id} (inputs={inputs})")
        logs.append(f"[开始] Skill: {skill.skill_id}")

        steps = skill.execution.steps
        total_steps = len(steps)

        for step_idx, step in enumerate(steps):
            # 中断检查
            if interrupt_check and interrupt_check():
                logs.append(f"[中断] 用户在第 {step_idx + 1} 步请求中断")
                logger.warning(f"Skill '{skill.skill_id}' 在第 {step_idx + 1} 步被中断")
                return ExecutionResult(
                    success=False,
                    outputs=outputs,
                    logs=logs,
                    execution_time_ms=int((time.monotonic() - start_time) * 1000),
                    error_message="用户中断",
                )

            # 解析参数模板
            resolved_params = self._resolve_params(step.params, inputs)

            # 记录
            step_desc = step.description or f"步骤 {step_idx + 1}: {step.tool}"
            logs.append(
                f"[步骤 {step_idx + 1}/{total_steps}] {step_desc} "
                f"→ {step.tool}({resolved_params})"
            )

            # 执行
            try:
                result = await self._execute_step(
                    step, resolved_params, step_idx
                )
                outputs.append({
                    "step": step_idx + 1,
                    "tool": step.tool,
                    "success": result[0],
                    "output": result[1],
                })
                logs.append(
                    f"  {'✅' if result[0] else '❌'} "
                    f"{'成功' if result[0] else '失败'}: {result[1][:200]}"
                )

                if not result[0]:
                    return ExecutionResult(
                        success=False,
                        outputs=outputs,
                        logs=logs,
                        execution_time_ms=int(
                            (time.monotonic() - start_time) * 1000
                        ),
                        error_message=f"步骤 {step_idx + 1} 失败: {result[1]}",
                    )

            except TimeoutError:
                logs.append(f"  ⏰ 步骤 {step_idx + 1} 超时 ({step.timeout_ms}ms)")
                return ExecutionResult(
                    success=False,
                    outputs=outputs,
                    logs=logs,
                    execution_time_ms=int(
                        (time.monotonic() - start_time) * 1000
                    ),
                    error_message=f"步骤 {step_idx + 1} 超时",
                )
            except Exception as e:
                logs.append(f"  💥 步骤 {step_idx + 1} 异常: {e}")
                return ExecutionResult(
                    success=False,
                    outputs=outputs,
                    logs=logs,
                    execution_time_ms=int(
                        (time.monotonic() - start_time) * 1000
                    ),
                    error_message=f"步骤 {step_idx + 1} 异常: {e}",
                )

        elapsed = int((time.monotonic() - start_time) * 1000)
        logs.append(f"[完成] 耗时 {elapsed}ms")
        logger.info(f"Skill '{skill.skill_id}' 执行成功 ({elapsed}ms)")

        return ExecutionResult(
            success=True,
            outputs=outputs,
            logs=logs,
            execution_time_ms=elapsed,
        )

    # ─── 参数解析 ──────────────────────────────────────

    def _resolve_params(
        self,
        params: dict[str, Any],
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """递归解析参数模板"""
        resolved = {}
        for key, value in params.items():
            resolved[key] = self._resolve_value(value, inputs)
        return resolved

    def _resolve_value(
        self, value: Any, inputs: dict[str, Any]
    ) -> Any:
        """递归解析单个值中的模板"""
        if isinstance(value, str):
            return self._resolve_template(value, inputs)
        elif isinstance(value, dict):
            return {
                k: self._resolve_value(v, inputs)
                for k, v in value.items()
            }
        elif isinstance(value, list):
            return [self._resolve_value(v, inputs) for v in value]
        return value

    def _resolve_template(
        self, text: str, inputs: dict[str, Any]
    ) -> str:
        """解析模板字符串，如 'QF${inputs.number}' → 'QF01'"""

        def _replace(match: re.Match) -> str:
            path = match.group(1).strip()
            # 支持嵌套路径: "position.x"
            parts = path.split(".")
            value: Any = inputs
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part, f"${{{path}}}")
                else:
                    return f"${{{path}}}"
            if value is None:
                return f"${{{path}}}"
            return str(value)

        return self.TEMPLATE_PATTERN.sub(_replace, text)

    # ─── 步骤执行 ──────────────────────────────────────

    async def _execute_step(
        self,
        step: SkillStep,
        params: dict[str, Any],
        step_idx: int,
    ) -> tuple[bool, str]:
        """执行单个步骤"""
        tool = self._tool_registry.get(step.tool)

        if tool is None:
            return (False, f"工具 '{step.tool}' 未注册")

        # 异步执行（支持同步/异步函数）
        if asyncio.iscoroutinefunction(tool):
            result = await asyncio.wait_for(
                tool(**params), timeout=step.timeout_ms / 1000
            )
        else:
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: tool(**params)
            )

        # 标准化结果
        if isinstance(result, tuple) and len(result) == 2:
            success, message = result
        elif isinstance(result, bool):
            success, message = result, "ok"
        elif isinstance(result, str):
            success, message = True, result
        elif isinstance(result, dict):
            success = result.get("success", True)
            message = json.dumps(result, ensure_ascii=False)
        else:
            success, message = True, str(result)

        return (success, message)

    # ─── 工具发现 ──────────────────────────────────────

    def discover_tools(self) -> list[str]:
        """探索可用的工具"""
        return list(self._tool_registry.keys())
