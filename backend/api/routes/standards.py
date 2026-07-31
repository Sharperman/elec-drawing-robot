"""
绘图规范 CRUD 路由
GET    /api/standards         - 列出所有规范
POST   /api/standards         - 创建规范
GET    /api/standards/{id}    - 获取规范详情
PUT    /api/standards/{id}    - 更新规范
DELETE /api/standards/{id}    - 删除规范
POST   /api/standards/activate - 激活规范
"""
from api.schemas import (
    ActivateStandardRequest,
    ApiResponse,
    CreateStandardRequest,
    DrawingStandardSchema,
    UpdateStandardRequest,
)
from fastapi import APIRouter, Depends, HTTPException
from knowledge.standards_manager import StandardsManager
from models.session import get_db
from sqlalchemy.orm import Session
from utils.error_codes import ErrorCode, get_error_message

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_standards(db: Session = Depends(get_db)) -> ApiResponse:
    """获取所有规范列表"""
    manager = StandardsManager(db)
    standards = manager.list_all()
    return ApiResponse(
        data=[DrawingStandardSchema.model_validate(s).model_dump() for s in standards]
    )


@router.get("/{standard_id}", response_model=ApiResponse)
async def get_standard(standard_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    """获取规范详情"""
    manager = StandardsManager(db)
    standard = manager.get_by_id(standard_id)
    if not standard:
        raise HTTPException(
            status_code=404,
            detail=get_error_message(ErrorCode.STANDARD_NOT_FOUND),
        )
    return ApiResponse(data=DrawingStandardSchema.model_validate(standard).model_dump())


@router.post("", response_model=ApiResponse)
async def create_standard(
    request: CreateStandardRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """创建新规范"""
    manager = StandardsManager(db)
    try:
        standard = manager.create(
            name=request.name,
            description=request.description,
            version=request.version,
            text_style=request.text_style,
            text_height=request.text_height,
            dim_style=request.dim_style,
            title_block=request.title_block,
        )
        return ApiResponse(data=DrawingStandardSchema.model_validate(standard).model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{standard_id}", response_model=ApiResponse)
async def update_standard(
    standard_id: int,
    request: UpdateStandardRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """更新规范"""
    manager = StandardsManager(db)
    update_data = request.model_dump(exclude_none=True)
    standard = manager.update(standard_id, **update_data)
    if not standard:
        raise HTTPException(
            status_code=404,
            detail=get_error_message(ErrorCode.STANDARD_NOT_FOUND),
        )
    return ApiResponse(data=DrawingStandardSchema.model_validate(standard).model_dump())


@router.delete("/{standard_id}", response_model=ApiResponse)
async def delete_standard(standard_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    """删除规范"""
    manager = StandardsManager(db)
    try:
        deleted = manager.delete(standard_id)
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail=get_error_message(ErrorCode.STANDARD_NOT_FOUND),
            )
        return ApiResponse(message="规范已删除")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/activate", response_model=ApiResponse)
async def activate_standard(
    request: ActivateStandardRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """激活指定规范"""
    manager = StandardsManager(db)
    standard = manager.activate(request.standard_id)
    if not standard:
        raise HTTPException(
            status_code=404,
            detail=get_error_message(ErrorCode.STANDARD_NOT_FOUND),
        )
    return ApiResponse(
        message=f"规范「{standard.name}」已激活",
        data=DrawingStandardSchema.model_validate(standard).model_dump(),
    )
