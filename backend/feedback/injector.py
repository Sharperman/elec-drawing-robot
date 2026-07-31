"""
规则注入器
将 LearnedRule 列表注入到 Agent 提示词中
"""

from loguru import logger


class RuleInjector:
    """
    将用户反馈提炼的规则注入到 Agent 提示词

    每次 Agent 调用前获取最新规则列表，
    格式化后作为补充上下文传递给 draw_agent.py
    """

    def get_active_rules_text(self, db_session=None) -> list[str]:
        """
        获取当前生效的规则文本列表

        Args:
            db_session: SQLAlchemy Session

        Returns:
            规则文本列表（供 build_system_prompt 使用）
        """
        if db_session is None:
            return []

        try:
            from models.feedback import LearnedRule

            rules = (
                db_session.query(LearnedRule)
                .filter_by(is_active=True)
                .order_by(LearnedRule.confidence.desc())
                .limit(10)  # 最多注入 10 条规则，避免 prompt 过长
                .all()
            )

            rule_texts: list[str] = []
            for rule in rules:
                text = f"【{rule.title}】{rule.rule_content}"
                rule_texts.append(text)
                # 增加应用计数
                rule.apply_count += 1

            if rule_texts:
                db_session.commit()

            logger.debug(f"Injecting {len(rule_texts)} learned rules into agent prompt")
            return rule_texts

        except Exception as e:
            logger.warning(f"Failed to get active rules: {e}")
            return []

    def format_for_prompt(self, rules: list[str]) -> str:
        """
        格式化规则列表为提示词片段

        Args:
            rules: 规则文本列表

        Returns:
            格式化字符串
        """
        if not rules:
            return ""

        lines = ["## 用户个性化规则（请严格遵守）"]
        for i, rule in enumerate(rules, 1):
            lines.append(f"{i}. {rule}")

        return "\n".join(lines)

    def inject(
        self,
        session_id: str,
        standards_context: str = "",
    ) -> tuple[str, list[str]]:
        """
        一站式获取规范上下文 + 学习规则（供 draw_agent 使用）

        Args:
            session_id: 会话 ID（暂未使用，保留扩展）
            standards_context: 已检索的规范上下文

        Returns:
            (standards_context, learned_rules_list) 元组
        """
        try:
            from models.session import get_session_local

            db = get_session_local()()
            try:
                rules = self.get_active_rules_text(db)
                return standards_context, rules
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Rule injection failed: {e}")
            return standards_context, []


# 全局单例
rule_injector = RuleInjector()
