"""
LLM 工厂服务

统一管理所有 LLM 实例创建，支持：
1. 主力 LLM（is_primary=True）和多模态 LLM（is_vision=True）独立配置
2. 运行时从数据库读取激活的 Provider
3. 向后兼容 config.py 的 fallback（数据库无记录时使用 .env）
"""

from langchain_openai import ChatOpenAI
from loguru import logger
from models.llm_provider import LLMProvider
from sqlalchemy.orm import Session


def _build_llm(
    api_key: str,
    base_url: str,
    model: str,
    temperature: float = 1.0,
    max_tokens: int | None = None,
    streaming: bool = False,
) -> ChatOpenAI:
    """构建 ChatOpenAI 实例（兼容 OpenAI 格式的 API）"""
    kwargs = dict(
        model=model,
        openai_api_key=api_key,
        openai_api_base=base_url,
        temperature=temperature,
        streaming=streaming,
    )
    # max_tokens=None 时不传，让模型自行决定上限
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatOpenAI(**kwargs)


def _get_provider_from_db(db: Session, vision: bool = False) -> LLMProvider | None:
    """从数据库获取当前激活的 Provider"""
    try:
        field = LLMProvider.is_vision if vision else LLMProvider.is_primary
        provider = (
            db.query(LLMProvider)
            .filter(field == True, LLMProvider.is_active == True)
            .first()
        )
        return provider
    except Exception as e:
        logger.warning(f"Failed to query LLM provider from DB: {e}")
        return None


def _get_env_fallback(vision: bool = False) -> dict:
    """从 config.py / .env 获取 fallback 配置"""
    from config import settings

    if vision:
        return {
            "api_key": settings.VISION_API_KEY or settings.OPENAI_API_KEY,
            "base_url": settings.VISION_BASE_URL or settings.OPENAI_BASE_URL,
            "model": settings.VISION_MODEL_NAME or settings.MODEL_NAME,
            "temperature": 1.0,
            "max_tokens": None,
        }

    return {
        "api_key": settings.OPENAI_API_KEY,
        "base_url": settings.OPENAI_BASE_URL,
        "model": settings.MODEL_NAME,
        "temperature": settings.LLM_TEMPERATURE,
        "max_tokens": None,
    }


def create_primary_llm(
    db: Session | None = None,
    streaming: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """
    创建主力 LLM 实例（用于文本推理/Agent 对话）

    优先级：数据库激活的 is_primary Provider > .env fallback

    Args:
        db: 数据库会话（可选，不传则只用 .env fallback）
        streaming: 是否启用流式输出
        temperature: 覆盖默认温度
        max_tokens: 覆盖默认最大 token 数

    Returns:
        ChatOpenAI 实例
    """
    if db:
        provider = _get_provider_from_db(db, vision=False)
        if provider:
            logger.debug(f"Using primary LLM from DB: {provider.provider_name}/{provider.model}")
            return _build_llm(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=provider.model,
                temperature=temperature if temperature is not None else provider.temperature,
                max_tokens=max_tokens if max_tokens is not None else provider.max_tokens,
                streaming=streaming,
            )

    # Fallback to .env
    cfg = _get_env_fallback(vision=False)
    logger.debug(f"Using primary LLM from .env: {cfg['model']}")
    return _build_llm(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        temperature=temperature if temperature is not None else cfg["temperature"],
        max_tokens=max_tokens if max_tokens is not None else cfg["max_tokens"],
        streaming=streaming,
    )


def create_vision_llm(
    db: Session | None = None,
    streaming: bool = False,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> ChatOpenAI:
    """
    创建多模态 LLM 实例（用于视觉分析/截图理解）

    优先级：数据库激活的 is_vision Provider > .env fallback

    Args:
        db: 数据库会话（可选，不传则只用 .env fallback）
        streaming: 是否启用流式输出
        temperature: 覆盖默认温度
        max_tokens: 覆盖默认最大 token 数

    Returns:
        ChatOpenAI 实例
    """
    if db:
        provider = _get_provider_from_db(db, vision=True)
        if provider:
            logger.debug(f"Using vision LLM from DB: {provider.provider_name}/{provider.model}")
            return _build_llm(
                api_key=provider.api_key,
                base_url=provider.base_url,
                model=provider.model,
                temperature=temperature if temperature is not None else provider.temperature,
                max_tokens=max_tokens if max_tokens is not None else provider.max_tokens,
                streaming=streaming,
            )

    # Fallback to .env（目前主力/多模态共用同一套）
    cfg = _get_env_fallback(vision=True)
    logger.debug(f"Using vision LLM from .env: {cfg['model']}")
    return _build_llm(
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        temperature=temperature if temperature is not None else cfg["temperature"],
        max_tokens=max_tokens if max_tokens is not None else cfg["max_tokens"],
        streaming=streaming,
    )


def get_llm_config_for_httpx(
    db: Session | None = None,
    vision: bool = False,
) -> dict:
    """
    获取 LLM 配置用于 httpx 裸调用（visual_reader 等不使用 LangChain 的场景）

    Returns:
        {"api_key": str, "base_url": str, "model": str}
    """
    if db:
        provider = _get_provider_from_db(db, vision=vision)
        if provider:
            return {
                "api_key": provider.api_key,
                "base_url": provider.base_url,
                "model": provider.model,
            }

    cfg = _get_env_fallback(vision=vision)
    return {
        "api_key": cfg["api_key"],
        "base_url": cfg["base_url"],
        "model": cfg["model"],
    }
