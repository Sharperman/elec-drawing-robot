"""
反馈规则提炼器
使用 LLM 从 UserFeedback 列表提炼出 LearnedRule
"""
import json
import uuid

from loguru import logger
from models.feedback import LearnedRule, UserFeedback
from sqlalchemy.orm import Session

REFINE_PROMPT = """你是电气工程智能绘图系统的学习模块。

以下是用户的反馈记录，请从中提炼出通用的操作规则，以提升未来的绘图准确性。

## 用户反馈记录
{feedback_list}

## 任务
请分析以上反馈，提炼出 1-3 条可操作的改进规则。每条规则需包含：
1. 规则标题（20字以内）
2. 规则内容（具体的行为指导，如"当用户提到某某时，应该...而不是..."）
3. 触发模式（用户通常怎么描述时触发此规则）

## 输出格式（JSON）
```json
[
  {{
    "title": "规则标题",
    "rule_content": "当xxx时，应该yyy，而不是zzz",
    "trigger_pattern": "触发此规则的用户意图描述"
  }}
]
```

只输出 JSON，不要其他内容。
"""


class FeedbackRefiner:
    """
    反馈规则提炼器
    使用 LLM 从积累的用户反馈中提炼可复用的操作规则
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    async def refine_all_unprocessed(self) -> list[LearnedRule]:
        """
        处理所有未处理的反馈，提炼规则

        Returns:
            新提炼的 LearnedRule 列表
        """
        unprocessed = (
            self.db.query(UserFeedback)
            .filter_by(is_processed=False)
            .limit(20)
            .all()
        )

        if not unprocessed:
            return []

        logger.info(f"Refining rules from {len(unprocessed)} feedbacks...")

        # 构建反馈摘要
        feedback_lines = []
        for fb in unprocessed:
            line = (
                f"[{fb.feedback_type}] "
                f"输入: {fb.original_input[:100]}\n"
                f"输出: {fb.agent_output[:100]}\n"
            )
            if fb.user_comment:
                line += f"用户说: {fb.user_comment}\n"
            if fb.correction:
                line += f"正确做法: {fb.correction}\n"
            feedback_lines.append(line)

        feedback_summary = "\n---\n".join(feedback_lines)

        # 调用 LLM 提炼规则
        rules = await self._call_llm_refine(feedback_summary)

        # 持久化规则
        new_rules: list[LearnedRule] = []
        if rules:
            source_ids = json.dumps([fb.id for fb in unprocessed])
            for rule_dict in rules:
                learned = LearnedRule(
                    rule_id=str(uuid.uuid4()),
                    title=rule_dict.get("title", "")[:200],
                    rule_content=rule_dict.get("rule_content", ""),
                    trigger_pattern=rule_dict.get("trigger_pattern", ""),
                    source_feedback_ids=source_ids,
                    confidence=0.8,
                    is_active=True,
                )
                self.db.add(learned)
                new_rules.append(learned)

        # 标记已处理
        for fb in unprocessed:
            fb.is_processed = True

        self.db.commit()
        for rule in new_rules:
            self.db.refresh(rule)

        logger.info(f"Refined {len(new_rules)} rules from {len(unprocessed)} feedbacks")
        return new_rules

    async def _call_llm_refine(self, feedback_summary: str) -> list[dict] | None:
        """调用 LLM 提炼规则"""
        try:
            from agent.llm_factory import create_primary_llm
            from langchain_core.messages import HumanMessage

            llm = create_primary_llm(
                temperature=0.3,
                max_tokens=2048,
            )

            prompt = REFINE_PROMPT.format(feedback_list=feedback_summary)
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content.strip()

            # 提取 JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            return json.loads(content)

        except Exception as e:
            logger.error(f"LLM rule refinement failed: {e}")
            return None

    def get_active_rules(self) -> list[LearnedRule]:
        """获取所有生效的学习规则"""
        return (
            self.db.query(LearnedRule)
            .filter_by(is_active=True)
            .order_by(LearnedRule.confidence.desc())
            .all()
        )
