"""
图元符号库 CRUD 路由
GET    /api/symbols           - 列出（分页/过滤）
POST   /api/symbols           - 创建
GET    /api/symbols/{id}      - 获取详情
PUT    /api/symbols/{id}      - 更新
DELETE /api/symbols/{id}      - 软删除
GET    /api/symbols/search    - 搜索
"""
from api.schemas import (
    ApiResponse,
    CreateSymbolRequest,
    SymbolSchema,
    UpdateSymbolRequest,
)
from fastapi import APIRouter, Depends, HTTPException, Query
from knowledge.symbol_library import SymbolLibrary
from models.session import get_db
from sqlalchemy.orm import Session
from utils.error_codes import ErrorCode, get_error_message

router = APIRouter()


@router.get("", response_model=ApiResponse)
async def list_symbols(
    category: str = Query(None, description="分类过滤"),
    search: str = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """获取图元符号列表（分页）"""
    lib = SymbolLibrary(db)
    items, total = lib.list_all(category=category, search=search, page=page, page_size=page_size)
    return ApiResponse(
        data={
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [SymbolSchema.model_validate(s).model_dump() for s in items],
        }
    )


@router.get("/search", response_model=ApiResponse)
async def search_symbols(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """搜索图元符号（模糊匹配名称）"""
    lib = SymbolLibrary(db)
    items = lib.search_by_name(q, limit=limit)
    return ApiResponse(
        data=[SymbolSchema.model_validate(s).model_dump() for s in items]
    )


@router.get("/{symbol_id}", response_model=ApiResponse)
async def get_symbol(symbol_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    """获取图元符号详情"""
    lib = SymbolLibrary(db)
    symbol = lib.get_by_id(symbol_id)
    if not symbol:
        raise HTTPException(
            status_code=404,
            detail=get_error_message(ErrorCode.SYMBOL_NOT_FOUND),
        )
    return ApiResponse(data=SymbolSchema.model_validate(symbol).model_dump())


@router.post("", response_model=ApiResponse)
async def create_symbol(
    request: CreateSymbolRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """创建自定义图元符号"""
    lib = SymbolLibrary(db)
    try:
        symbol = lib.create(
            symbol_id=request.symbol_id,
            name=request.name,
            name_en=request.name_en,
            category=request.category,
            description=request.description,
            block_name=request.block_name,
            layer=request.layer,
            width=request.width,
            height=request.height,
            tags=request.tags,
        )
        return ApiResponse(data=SymbolSchema.model_validate(symbol).model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{symbol_id}", response_model=ApiResponse)
async def update_symbol(
    symbol_id: str,
    request: UpdateSymbolRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """更新图元符号"""
    lib = SymbolLibrary(db)
    update_data = request.model_dump(exclude_none=True)
    symbol = lib.update(symbol_id, **update_data)
    if not symbol:
        raise HTTPException(
            status_code=404,
            detail=get_error_message(ErrorCode.SYMBOL_NOT_FOUND),
        )
    return ApiResponse(data=SymbolSchema.model_validate(symbol).model_dump())


@router.delete("/{symbol_id}", response_model=ApiResponse)
async def delete_symbol(symbol_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    """软删除图元符号"""
    lib = SymbolLibrary(db)
    deleted = lib.delete(symbol_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=get_error_message(ErrorCode.SYMBOL_NOT_FOUND),
        )
    return ApiResponse(message=f"图元符号 '{symbol_id}' 已删除")
