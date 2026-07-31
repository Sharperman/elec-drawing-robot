"""
用户反馈收集器
接收用户反馈并持久化到 SQLite
"""

from loguru import logger
from models.feedback import UserFeedback
from sqlalchemy.orm import Session


class FeedbackCollector:
    """用户反馈收集器"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def collect(
        self,
        session_id: str,
        feedback_type: str,
        original_input: str = "",
        agent_output: str = "",
        user_comment: str = "",
        correction: str | None = None,
        rating: int | None = None,
        message_id: int | None = None,
    ) -> UserFeedback:
        """
        收集用户反馈并保存到数据库

        Args:
            session_id: 会话 ID
            feedback_type: 反馈类型（positive/negative/correction/suggestion）
            original_input: 用户原始输入
            agent_output: Agent 的回复/操作
            user_comment: 用户反馈说明
            correction: 用户提供的正确做法
            rating: 满意度评分（1-5）
            message_id: 关联消息 ID

        Returns:
            UserFeedback ORM 实例
        """
        feedback = UserFeedback(
            session_id=session_id,
            message_id=message_id,
            feedback_type=feedback_type,
            original_input=original_input,
            agent_output=agent_output,
            user_comment=user_comment,
            correction=correction,
            rating=rating,
            is_processed=False,
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)

        logger.info(
            f"Feedback collected: type={feedback_type} "
            f"session={session_id} id={feedback.id}"
        )

        # 检查是否触发规则提炼
        self._check_refine_trigger(session_id)

        return feedback

    def _check_refine_trigger(self, session_id: str) -> None:
        """
        检查未处理的反馈数量，达到阈值时触发规则提炼

        使用异步任务避免阻塞 API 请求。
        """
        from config import settings

        unprocessed_count = (
            self.db.query(UserFeedback)
            .filter_by(is_processed=False)
            .count()
        )

        if unprocessed_count >= settings.FEEDBACK_REFINE_THRESHOLD:
            logger.info(
                f"Feedback threshold reached ({unprocessed_count}), "
                f"triggering rule refinement..."
            )
            # 异步触发提炼（不阻塞当前请求）
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_refine())
            except RuntimeError:
                # 无运行中的事件循环时忽略（同步调用场景）
                pass

    async def _async_refine(self) -> None:
        """异步执行规则提炼"""
        try:
            from feedback.refiner import FeedbackRefiner
            from models.session import get_session_local

            db = get_session_local()()
            try:
                refiner = FeedbackRefiner(db)
                await refiner.refine_all_unprocessed()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Async feedback refinement failed: {e}")

    def get_feedbacks(
        self,
        session_id: str | None = None,
        feedback_type: str | None = None,
        processed: bool | None = None,
        limit: int = 50,
    ) -> list[UserFeedback]:
        """
        查询反馈列表

        Args:
            session_id: 按会话过滤
            feedback_type: 按类型过滤
            processed: 按处理状态过滤
            limit: 最多返回条数

        Returns:
            UserFeedback 列表
        """
        query = self.db.query(UserFeedback)
        if session_id:
            query = query.filter_by(session_id=session_id)
        if feedback_type:
            query = query.filter_by(feedback_type=feedback_type)
        if processed is not None:
            query = query.filter_by(is_processed=processed)

        return query.order_by(UserFeedback.created_at.desc()).limit(limit).all()
