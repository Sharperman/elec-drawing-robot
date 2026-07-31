"""
LLM Provider 管理路由

/api/llm/providers      GET     - 获取所有 Provider 列表
/api/llm/providers      POST    - 创建或更新 Provider（upsert）
/api/llm/providers/{id} DELETE  - 删除 Provider
/api/llm/providers/{id}/activate POST - 激活 Provider（设为 primary/vision）
/api/llm/providers/{id}/test    POST - 测试 Provider 连接
/api/llm/env              POST   - 将当前激活配置同步到 .env
"""
from datetime import datetime

from api.schemas import ApiResponse
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from models.llm_provider import LLMProvider
from models.session import get_db
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

router = APIRouter()


# ─── 请求/响应模型 ──────────────────────────────────────────────

class ProviderCreate(BaseModel):
    provider_name: str = Field(..., min_length=1, max_length=100, description="供应商名称")
    base_url: str = Field(..., min_length=1, max_length=500, description="API Base URL")
    api_key: str = Field(..., min_length=1, description="API Key")
    model: str = Field(..., min_length=1, max_length=100, description="模型名称")
    temperature: float = Field(default=1.0, ge=0.0, le=2.0)


class ProviderUpdate(BaseModel):
    provider_name: str | None = Field(None, max_length=100)
    base_url: str | None = Field(None, max_length=500)
    api_key: str | None = None
    model: str | None = Field(None, max_length=100)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    is_active: bool | None = None


class ActivateRequest(BaseModel):
    role: str = Field(..., description="激活角色: primary=主力LLM, vision=多模态LLM")


# ─── 路由 ───────────────────────────────────────────────────────

@router.get("/providers", response_model=ApiResponse)
def list_providers(db: Session = Depends(get_db)) -> ApiResponse:
    """获取所有 LLM Provider（API Key 自动消隐）"""
    providers = (
        db.query(LLMProvider)
        .order_by(LLMProvider.is_primary.desc(), LLMProvider.is_vision.desc(), LLMProvider.updated_at.desc())
        .all()
    )
    return ApiResponse(data=[p.to_dict(mask_key=True) for p in providers])


@router.post("/providers", response_model=ApiResponse)
def upsert_provider(
    body: ProviderCreate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    创建或更新 LLM Provider

    规则：
    - 同一 (base_url, model) 组合视为同一 Provider，新写入覆盖旧 API Key
    - 如果是第一个 Provider，自动设为 is_primary=True
    """
    # 查找已存在的同 (base_url, model) Provider
    existing = (
        db.query(LLMProvider)
        .filter(LLMProvider.base_url == body.base_url, LLMProvider.model == body.model)
        .first()
    )

    if existing:
        # 更新现有记录
        existing.provider_name = body.provider_name
        existing.api_key = body.api_key
        existing.temperature = body.temperature
        existing.updated_at = datetime.utcnow()
        provider = existing
        logger.info(f"Updated LLM provider: {provider.provider_name}/{provider.model}")
    else:
        # 创建新记录
        provider = LLMProvider(
            provider_name=body.provider_name,
            base_url=body.base_url,
            api_key=body.api_key,
            model=body.model,
            temperature=body.temperature,
        )

        # 如果是第一个 Provider，自动设为主力 LLM
        count = db.query(LLMProvider).count()
        if count == 0:
            provider.is_primary = True
            logger.info(f"First provider, auto-set as primary: {provider.provider_name}/{provider.model}")

        db.add(provider)

    db.commit()
    db.refresh(provider)

    # 自动同步到 .env
    _sync_to_env(db)

    return ApiResponse(data=provider.to_dict(mask_key=True))


@router.get("/providers/{provider_id}", response_model=ApiResponse)
def get_provider(
    provider_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """获取单个 Provider 详情（API Key 消隐）"""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    return ApiResponse(data=provider.to_dict(mask_key=True))


@router.delete("/providers/{provider_id}", response_model=ApiResponse)
def delete_provider(
    provider_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """删除 LLM Provider"""
    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    was_primary = provider.is_primary
    was_vision = provider.is_vision

    db.delete(provider)
    db.commit()

    # 如果删除的是激活的 Provider，自动选择下一个
    if was_primary:
        next_primary = db.query(LLMProvider).filter(LLMProvider.is_active == True).first()
        if next_primary:
            next_primary.is_primary = True
            db.commit()
            logger.info(f"Auto-assigned primary to: {next_primary.provider_name}/{next_primary.model}")

    if was_vision:
        next_vision = db.query(LLMProvider).filter(LLMProvider.is_active == True).first()
        if next_vision:
            next_vision.is_vision = True
            db.commit()
            logger.info(f"Auto-assigned vision to: {next_vision.provider_name}/{next_vision.model}")

    _sync_to_env(db)

    return ApiResponse(data={"deleted": provider_id})


@router.post("/providers/{provider_id}/activate", response_model=ApiResponse)
def activate_provider(
    provider_id: int,
    body: ActivateRequest,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    激活 Provider 为特定角色

    规则：
    - role=primary: 取消所有其他 is_primary，设置当前为 primary
    - role=vision: 取消所有其他 is_vision，设置当前为 vision
    """
    if body.role not in ("primary", "vision"):
        raise HTTPException(status_code=400, detail="role must be 'primary' or 'vision'")

    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    if body.role == "primary":
        # 取消所有其他 primary
        db.query(LLMProvider).filter(LLMProvider.is_primary == True).update({"is_primary": False})
        provider.is_primary = True
        logger.info(f"Activated primary LLM: {provider.provider_name}/{provider.model}")
    else:
        # 取消所有其他 vision
        db.query(LLMProvider).filter(LLMProvider.is_vision == True).update({"is_vision": False})
        provider.is_vision = True
        logger.info(f"Activated vision LLM: {provider.provider_name}/{provider.model}")

    db.commit()
    db.refresh(provider)

    _sync_to_env(db)

    return ApiResponse(data=provider.to_dict(mask_key=True))


@router.post("/providers/{provider_id}/test", response_model=ApiResponse)
def test_provider(
    provider_id: int,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    测试 Provider 连接

    发送一个简单的 /chat/completions 请求验证 API 可用性
    """
    import httpx

    provider = db.query(LLMProvider).filter(LLMProvider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    api_url = f"{provider.base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": provider.model,
        "messages": [{"role": "user", "content": "Hello, respond with 'ok' only."}],
        "max_tokens": 10,
        "temperature": 0,
    }

    start = datetime.utcnow()
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(api_url, headers=headers, json=payload)
            elapsed = (datetime.utcnow() - start).total_seconds()

        if response.status_code == 200:
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            provider.test_status = "ok"
            provider.last_tested_at = datetime.utcnow()
            db.commit()
            return ApiResponse(data={
                "status": "ok",
                "elapsed_ms": round(elapsed * 1000),
                "model": data.get("model", provider.model),
                "response": content[:100],
            })
        else:
            error_msg = f"HTTP {response.status_code}"
            try:
                error_detail = response.json()
                error_msg += f": {str(error_detail)[:200]}"
            except Exception:
                error_msg += f": {response.text[:200]}"

            provider.test_status = "fail"
            provider.last_tested_at = datetime.utcnow()
            db.commit()
            return ApiResponse(code=1, message=error_msg, data={"status": "fail", "error": error_msg})

    except httpx.TimeoutException:
        provider.test_status = "fail"
        provider.last_tested_at = datetime.utcnow()
        db.commit()
        return ApiResponse(code=1, message="连接超时", data={"status": "fail", "error": "连接超时（30秒）"})
    except Exception as e:
        provider.test_status = "fail"
        provider.last_tested_at = datetime.utcnow()
        db.commit()
        return ApiResponse(code=1, message=str(e)[:200], data={"status": "fail", "error": str(e)[:200]})


@router.post("/env", response_model=ApiResponse)
def sync_to_env(db: Session = Depends(get_db)) -> ApiResponse:
    """手动同步当前激活配置到 .env 文件"""
    result = _sync_to_env(db)
    return ApiResponse(data=result)


# ─── 内部函数 ───────────────────────────────────────────────────

def _sync_to_env(db: Session) -> dict:
    """
    将当前激活的 Provider 配置同步到项目 .env 文件

    写入内容：
    - OPENAI_API_KEY = primary provider 的 api_key
    - MODEL_NAME = primary provider 的 model
    - OPENAI_BASE_URL = primary provider 的 base_url

    同时写入多模态配置（如有独立的 vision provider）：
    - VISION_MODEL_NAME = vision provider 的 model（如果与 primary 不同）
    """
    from pathlib import Path

    primary = (
        db.query(LLMProvider)
        .filter(LLMProvider.is_primary == True, LLMProvider.is_active == True)
        .first()
    )
    vision = (
        db.query(LLMProvider)
        .filter(LLMProvider.is_vision == True, LLMProvider.is_active == True)
        .first()
    )

    if not primary:
        return {"synced": False, "reason": "没有激活的主力 LLM Provider"}

    # 定位 .env 文件
    from config import ROOT_DIR
    env_path = Path(ROOT_DIR) / ".env"

    # 读取当前 .env
    try:
        with open(env_path, encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        lines = []

    # 需要更新的字段
    updates = {
        "OPENAI_API_KEY": primary.api_key,
        "MODEL_NAME": primary.model,
        "OPENAI_BASE_URL": primary.base_url,
    }

    # 如果有独立的 vision provider，写入 VISION_MODEL_NAME
    if vision and vision.model != primary.model:
        updates["VISION_MODEL_NAME"] = vision.model
        updates["VISION_API_KEY"] = vision.api_key
        updates["VISION_BASE_URL"] = vision.base_url

    # 更新或追加
    updated_keys = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    # 追加未出现过的 key
    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    # 写回
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    logger.info(f".env synced: {list(updates.keys())}")
    return {
        "synced": True,
        "primary": f"{primary.provider_name}/{primary.model}",
        "vision": f"{vision.provider_name}/{vision.model}" if vision else None,
        "updated_keys": list(updates.keys()),
    }
