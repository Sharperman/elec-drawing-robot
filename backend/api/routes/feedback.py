"""
用户反馈路由
POST /api/feedback       - 提交反馈
GET  /api/feedback/rules - 获取已提炼的规则
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.schemas import ApiResponse, FeedbackRequest, LearnedRuleSchema
from models.session import get_db
from feedback.collector import FeedbackCollector
from utils.error_codes import ErrorCode

router = APIRouter()


@router.post("", response_model=ApiResponse)
async def submit_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """提交用户反馈"""
    collector = FeedbackCollector(db)
    feedback = collector.collect(
        session_id=request.session_id,
        feedback_type=request.feedback_type,
        original_input=request.original_input,
        agent_output=request.agent_output,
        user_comment=request.user_comment,
        correction=request.correction,
        rating=request.rating,
        message_id=request.message_id,
    )
    return ApiResponse(
        message="反馈已收到，感谢您的反馈！",
        data={"feedback_id": feedback.id},
    )


@router.get("/rules", response_model=ApiResponse)
async def get_learned_rules(db: Session = Depends(get_db)) -> ApiResponse:
    """获取所有已提炼的学习规则"""
    from models.feedback import LearnedRule
    rules = (
        db.query(LearnedRule)
        .filter_by(is_active=True)
        .order_by(LearnedRule.confidence.desc())
        .all()
    )
    return ApiResponse(
        data=[LearnedRuleSchema.model_validate(r).model_dump() for r in rules]
    )


@router.post("/refine", response_model=ApiResponse)
async def trigger_refine(db: Session = Depends(get_db)) -> ApiResponse:
    """手动触发规则提炼（管理员用）"""
    from feedback.refiner import FeedbackRefiner
    refiner = FeedbackRefiner(db)
    new_rules = await refiner.refine_all_unprocessed()
    return ApiResponse(
        message=f"提炼完成，新增 {len(new_rules)} 条规则",
        data={"new_rules_count": len(new_rules)},
    )
