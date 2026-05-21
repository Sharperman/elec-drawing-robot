"""
意图分类器
快速识别用户意图：绘图指令/查询/规范配置/图片识别/一般对话
"""
from enum import Enum
from typing import Optional

from loguru import logger


class IntentType(str, Enum):
    """意图类型枚举"""
    DRAW = "DRAW"           # 绘图指令
    QUERY = "QUERY"         # 查询图纸状态
    CONFIG = "CONFIG"       # 配置规范/设置
    RECOGNIZE = "RECOGNIZE" # 图片识别
    CONFIRM = "CONFIRM"     # 确认/取消操作
    CHAT = "CHAT"           # 一般对话


# 基于规则的快速意图分类关键词
_DRAW_KEYWORDS = [
    "插入", "添加", "绘制", "画", "放置", "新增", "创建图元",
    "断路器", "变压器", "母线", "接地", "导线", "连接", "电缆",
    "移动", "删除", "修改位置", "旋转", "缩放",
    "insert", "draw", "add",
]

_QUERY_KEYWORDS = [
    "查询", "查看", "显示", "列出", "有哪些", "什么设备", "图纸上",
    "当前状态", "统计", "有多少",
    "query", "show", "list",
]

_CONFIG_KEYWORDS = [
    "配置", "设置", "规范", "图层", "颜色", "线型", "线宽",
    "修改图层", "激活规范", "切换规范",
    "config", "standard", "layer",
]

_RECOGNIZE_KEYWORDS = [
    "识别", "分析图片", "解析图纸", "OCR", "检测",
    "这张图", "上传的图", "图片里",
    "recognize", "detect",
]

_CONFIRM_KEYWORDS = [
    "确认", "执行", "好的", "是的", "继续", "取消", "不要",
    "confirm", "yes", "ok", "no", "cancel",
]


class IntentParser:
    """
    意图分类器
    
    优先使用规则匹配（快速、无 LLM 成本），
    规则无法确定时降级到 LLM 分类。
    """

    def classify(
        self,
        user_input: str,
        has_image: bool = False,
    ) -> IntentType:
        """
        分类用户意图

        Args:
            user_input: 用户输入文字
            has_image: 是否附带图片

        Returns:
            IntentType 枚举值
        """
        # 有图片时优先识别意图
        if has_image:
            return IntentType.RECOGNIZE

        text = user_input.strip().lower()

        # 快速规则匹配
        intent = self._rule_based_classify(text)
        if intent:
            logger.debug(f"Intent classified by rules: {intent.value}")
            return intent

        # 默认回退到 CHAT
        logger.debug("Intent fallback to CHAT")
        return IntentType.CHAT

    async def classify_async(
        self,
        user_input: str,
        has_image: bool = False,
        use_llm: bool = True,
    ) -> IntentType:
        """
        异步意图分类（支持 LLM 辅助）

        Args:
            user_input: 用户输入
            has_image: 是否附带图片
            use_llm: 是否使用 LLM 进行精确分类

        Returns:
            IntentType
        """
        if has_image:
            return IntentType.RECOGNIZE

        text = user_input.strip().lower()

        # 规则优先
        intent = self._rule_based_classify(text)
        if intent:
            return intent

        # LLM 辅助分类
        if use_llm:
            try:
                llm_intent = await self._llm_classify(user_input)
                if llm_intent:
                    return llm_intent
            except Exception as e:
                logger.warning(f"LLM intent classification failed: {e}")

        return IntentType.CHAT

    def _rule_based_classify(self, text: str) -> Optional[IntentType]:
        """基于关键词的规则分类"""
        if any(kw in text for kw in _CONFIRM_KEYWORDS) and len(text) < 30:
            return IntentType.CONFIRM

        if any(kw in text for kw in _QUERY_KEYWORDS):
            return IntentType.QUERY

        if any(kw in text for kw in _DRAW_KEYWORDS):
            return IntentType.DRAW

        if any(kw in text for kw in _CONFIG_KEYWORDS):
            return IntentType.CONFIG

        if any(kw in text for kw in _RECOGNIZE_KEYWORDS):
            return IntentType.RECOGNIZE

        return None

    async def _llm_classify(self, user_input: str) -> Optional[IntentType]:
        """使用 LLM 进行精确意图分类"""
        from langchain_openai import ChatOpenAI
        from langchain_core.messages import HumanMessage
        from config import settings
        from agent.prompts.system_prompt import INTENT_CLASSIFICATION_PROMPT

        llm = ChatOpenAI(
            model=settings.MODEL_NAME,
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_BASE_URL,
            temperature=0.0,
            max_tokens=20,
        )

        prompt = INTENT_CLASSIFICATION_PROMPT.format(user_input=user_input)
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        result = response.content.strip().upper()

        try:
            return IntentType(result)
        except ValueError:
            return None


# 全局单例
intent_parser = IntentParser()
