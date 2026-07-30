"""
Skill Auto-Creator — 自动从成功任务提取可复用 Skill

触发条件：
1. Agent 完成任务（success）
2. 任务步骤数 >= 2（有意义）
3. 用户明确说"保存为 Skill"或置信度足够高
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

from hermes.models.skill import (
    HermesSkill,
    SkillMetadata,
    SkillTrigger,
    SkillStep,
    SkillExecutionConfig,
    SkillInputSchema,
    SkillInputProperty,
    SkillCategory,
    SkillStatus,
    ExecutionResult,
)


class SkillAutoCreator:
    """
    Skill 自动创建器

    流程:
    1. 收集执行轨迹（工具调用序列）
    2. 使用 LLM 生成 Skill 元数据（名称、描述、触发词）
    3. 生成 steps 配置
    4. 返回 HermesSkill 对象（待人工确认）
    """

    # 步骤数少于该值不自动创建
    MIN_STEPS = 2

    # 需要人工确认的置信度阈值
    AUTO_CONFIRM_THRESHOLD = 0.9

    def __init__(self, llm_client: Optional[Any] = None):
        self._llm = llm_client

    def set_llm(self, llm_client: Any) -> None:
        """设置 LLM 客户端"""
        self._llm = llm_client

    # ─── 公开 API ─────────────────────────────────────

    async def create_from_execution(
        self,
        task_description: str,
        execution_trace: List[Dict[str, Any]],
        user_confirmation: Optional[bool] = None,
    ) -> AutoGenResult:
        """
        从执行轨迹创建 Skill

        Args:
            task_description: 用户的任务描述
            execution_trace: 执行轨迹，每步包含 {tool, params, result}
            user_confirmation: 用户是否明确要求保存

        Returns:
            AutoGenResult
        """
        steps = [s for s in execution_trace
                 if s.get("tool") and s.get("success", True)]

        if len(steps) < self.MIN_STEPS:
            return AutoGenResult(
                skill=None,
                confidence=0.0,
                message=f"步骤数 ({len(steps)}) 太少，无需自动创建 Skill",
                requires_confirmation=False,
            )

        # 生成参数 schema
        inputs_schema = self._infer_inputs(steps)

        # 使用 LLM 生成元数据（如果有 LLM）
        if self._llm:
            metadata, confidence = await self._llm_generate_metadata(
                task_description, steps
            )
        else:
            metadata, confidence = self._rule_generate_metadata(
                task_description, steps
            )

        # 生成 steps
        skill_steps = []
        for s in steps:
            skill_steps.append(SkillStep(
                tool=s["tool"],
                params=s.get("params", {}),
                description=s.get("description", f"调用 {s['tool']}"),
            ))

        # 清洗 skill_id
        skill_id = self._clean_skill_id(metadata.get("name", task_description))

        # 构建 HermesSkill
        skill = HermesSkill(
            skill_id=skill_id,
            metadata=SkillMetadata(
                name=skill_id,
                description=metadata.get("description", task_description),
                author="hermes-auto-creator",
                created_at=datetime.utcnow().isoformat(),
                updated_at=datetime.utcnow().isoformat(),
                version="1.0.0",
            ),
            category=SkillCategory.AUTOGEN,
            status=SkillStatus.ACTIVE,
            triggers=SkillTrigger(
                patterns=metadata.get("triggers", []),
                confidence_threshold=metadata.get(
                    "confidence_threshold", 0.7
                ),
            ),
            inputs=inputs_schema,
            execution=SkillExecutionConfig(
                type="python", entry="execute.py", steps=skill_steps
            ),
        )

        # 是否需人工确认
        # 用户明确要求 或 置信度足够高 → 自动确认
        requires_confirmation = True
        if user_confirmation is True:
            requires_confirmation = False
            confidence = max(confidence, 0.95)
        elif confidence >= self.AUTO_CONFIRM_THRESHOLD:
            requires_confirmation = False

        result = AutoGenResult(
            skill=skill,
            confidence=round(confidence, 2),
            message=self._generate_summary(skill, steps),
            requires_confirmation=requires_confirmation,
        )

        logger.info(
            f"Skill 自动创建: {skill_id} "
            f"(confidence={confidence}, confirm={requires_confirmation})"
        )

        return result

    # ─── LLM 驱动元数据生成 ──────────────────────────

    async def _llm_generate_metadata(
        self,
        task_description: str,
        steps: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], float]:
        """使用 LLM 分析任务并生成 Skill 元数据"""
        if not self._llm:
            return self._rule_generate_metadata(task_description, steps)

        prompt = self._build_llm_prompt(task_description, steps)

        try:
            response = await self._llm.ainvoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)

            # 从回复中提取 JSON
            metadata = self._extract_json(text)
            if metadata:
                confidence = metadata.get("confidence", 0.8)
                return metadata, confidence
        except Exception as e:
            logger.warning(f"LLM 生成元数据失败，回退到规则生成: {e}")

        return self._rule_generate_metadata(task_description, steps)

    def _build_llm_prompt(
        self,
        task: str,
        steps: List[Dict[str, Any]],
    ) -> List[Dict[str, str]]:
        """构建 LLM Prompt"""
        steps_str = json.dumps(steps, ensure_ascii=False, indent=2)
        return [
            {
                "role": "system",
                "content": (
                    "你是一个 Skill 生成器。你的任务是从成功执行的任务中提取"
                    "可复用的 Skill。请分析以下任务和执行轨迹，生成 Skill 元数据。"
                    "\n\n仅返回 JSON，不要其他文字："
                    "\n{"
                    "\n  \"name\": \"简短英文名，如 draw_breaker\","
                    "\n  \"description\": \"中文描述\","
                    "\n  \"triggers\": [\"触发词1\", \"触发词2\"],"
                    "\n  \"confidence_threshold\": 0.8,"
                    "\n  \"confidence\": 0.9"
                    "\n}"
                ),
            },
            {
                "role": "user",
                "content": f"任务: {task}\n\n执行步骤:\n{steps_str}",
            },
        ]

    # ─── 规则驱动元数据生成（Fallback） ─────────────

    def _rule_generate_metadata(
        self,
        task_description: str,
        steps: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], float]:
        """基于规则的元数据生成（无需 LLM）"""
        # 从任务描述提取关键词作为触发词
        triggers = self._extract_triggers(task_description)

        # 从步骤推断名称
        tools_used = [s["tool"] for s in steps if "tool" in s]
        tool_summary = "_".join(tools_used[:3])

        name = self._clean_skill_id(
            f"{tool_summary}_{len(steps)}steps"
        )

        metadata = {
            "name": name,
            "description": task_description[:200],
            "triggers": triggers,
            "confidence_threshold": 0.7,
            "confidence": 0.6,  # 规则生成的置信度较低
        }
        return metadata, 0.6

    # ─── 辅助方法 ─────────────────────────────────────

    def _infer_inputs(
        self, steps: List[Dict[str, Any]]
    ) -> SkillInputSchema:
        """从步骤参数推断输入 Schema"""
        properties: Dict[str, SkillInputProperty] = {}
        required: List[str] = []

        for step in steps:
            params = step.get("params", {})
            if not isinstance(params, dict):
                continue
            for key, value in params.items():
                if key not in properties:
                    # 跳过含具体数值的参数（如坐标）
                    if isinstance(value, (int, float)) and abs(value) > 100:
                        continue
                    properties[key] = SkillInputProperty(
                        type=self._infer_type(value),
                        description=f"参数 {key}",
                        default=value if not isinstance(value, str) else None,
                    )
                    required.append(key)

        return SkillInputSchema(properties=properties, required=required)

    def _infer_type(self, value: Any) -> str:
        """推断参数类型"""
        if isinstance(value, bool):
            return "boolean"
        elif isinstance(value, int):
            return "integer"
        elif isinstance(value, float):
            return "number"
        elif isinstance(value, dict):
            return "object"
        elif isinstance(value, list):
            return "array"
        return "string"

    def _extract_triggers(self, text: str) -> List[str]:
        """从文本提取触发词"""
        # 基本清洗
        text = text.strip().strip("。！？，.")

        triggers = [text]

        # 常见动词开头拆分
        verbs = ["画", "绘制", "插入", "添加", "创建", "查询",
                 "查找", "删除", "修改", "导出", "检查"]
        for v in verbs:
            if text.startswith(v):
                remainder = text[len(v):].strip()
                if remainder:
                    triggers.append(remainder)
                break

        # 英文关键词
        eng_keywords = re.findall(r"[a-zA-Z_]+", text)
        if eng_keywords:
            triggers.append("_".join(eng_keywords[:3]).lower())

        # 去重
        seen = set()
        unique = []
        for t in triggers:
            t_lower = t.lower()
            if t_lower not in seen:
                seen.add(t_lower)
                unique.append(t)

        return unique[:5]

    def _clean_skill_id(self, name: str) -> str:
        """生成合法的 skill_id"""
        # 中文转拼音式英文（简化：直接取首字母）
        cleaned = re.sub(r"[^\w\s-]", "", name)
        cleaned = cleaned.strip().lower()
        cleaned = re.sub(r"[\s-]+", "_", cleaned)

        # 如果全是中文，加前缀
        if not cleaned or not re.search(r"[a-z]", cleaned):
            cleaned = f"skill_{len(cleaned)}"

        # 限制长度
        return cleaned[:64]

    def _extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """从文本中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试从 ```json ... ``` 中提取
        match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试从 { ... } 中提取
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _generate_summary(
        self,
        skill: HermesSkill,
        steps: List[Dict[str, Any]],
    ) -> str:
        """生成摘要"""
        return (
            f"Skill 已创建: {skill.skill_id}\n"
            f"描述: {skill.metadata.description}\n"
            f"步骤: {len(steps)} 步\n"
            f"触发词: {skill.triggers.patterns if skill.triggers else '无'}"
        )


class AutoGenResult:
    """自动创建结果"""

    def __init__(
        self,
        skill: Optional[HermesSkill],
        confidence: float,
        message: str,
        requires_confirmation: bool = True,
    ):
        self.skill = skill
        self.confidence = confidence
        self.message = message
        self.requires_confirmation = requires_confirmation

    def to_dict(self) -> Dict[str, Any]:
        """转为字典"""
        return {
            "skill_id": self.skill.skill_id if self.skill else None,
            "skill": self.skill.to_dict() if self.skill else None,
            "confidence": self.confidence,
            "message": self.message,
            "requires_confirmation": self.requires_confirmation,
        }
