"""
统一错误码常量
前后端共享的错误码定义
"""


class ErrorCode:
    """错误码常量类"""

    # ---- 通用错误 (1xxx) ----
    SUCCESS = 0
    UNKNOWN_ERROR = 1000
    VALIDATION_ERROR = 1001
    NOT_FOUND = 1002
    ALREADY_EXISTS = 1003
    PERMISSION_DENIED = 1004
    RATE_LIMITED = 1005

    # ---- LLM / Agent 错误 (2xxx) ----
    LLM_API_ERROR = 2000
    LLM_TIMEOUT = 2001
    LLM_CONTEXT_TOO_LONG = 2002
    AGENT_MAX_ITERATIONS = 2003
    AGENT_PARSE_ERROR = 2004
    AGENT_TOOL_ERROR = 2005
    INVALID_API_KEY = 2006

    # ---- AutoCAD 错误 (3xxx) ----
    AUTOCAD_NOT_CONNECTED = 3000
    AUTOCAD_CONNECTION_FAILED = 3001
    AUTOCAD_DRAWING_NOT_OPEN = 3002
    AUTOCAD_BLOCK_NOT_FOUND = 3003
    AUTOCAD_ENTITY_NOT_FOUND = 3004
    AUTOCAD_OPERATION_FAILED = 3005
    AUTOCAD_COM_ERROR = 3006
    AUTOCAD_LAYER_ERROR = 3007

    # ---- 知识库错误 (4xxx) ----
    SYMBOL_NOT_FOUND = 4000
    STANDARD_NOT_FOUND = 4001
    VECTOR_STORE_ERROR = 4002
    EMBED_ERROR = 4003

    # ---- 识别错误 (5xxx) ----
    RECOGNITION_FAILED = 5000
    MODEL_NOT_LOADED = 5001
    IMAGE_INVALID = 5002
    IMAGE_TOO_LARGE = 5003
    NO_ELEMENTS_DETECTED = 5004

    # ---- 数据库错误 (6xxx) ----
    DB_ERROR = 6000
    DB_CONSTRAINT_ERROR = 6001

    # ---- 会话错误 (7xxx) ----
    SESSION_NOT_FOUND = 7000
    SESSION_EXPIRED = 7001


# 错误码消息映射
ERROR_MESSAGES: dict[int, str] = {
    ErrorCode.SUCCESS: "成功",
    ErrorCode.UNKNOWN_ERROR: "未知错误",
    ErrorCode.VALIDATION_ERROR: "请求参数验证失败",
    ErrorCode.NOT_FOUND: "资源不存在",
    ErrorCode.ALREADY_EXISTS: "资源已存在",
    ErrorCode.PERMISSION_DENIED: "权限不足",
    ErrorCode.RATE_LIMITED: "请求过于频繁",

    ErrorCode.LLM_API_ERROR: "LLM API 调用失败",
    ErrorCode.LLM_TIMEOUT: "LLM API 请求超时",
    ErrorCode.LLM_CONTEXT_TOO_LONG: "对话上下文过长",
    ErrorCode.AGENT_MAX_ITERATIONS: "Agent 达到最大迭代次数",
    ErrorCode.AGENT_PARSE_ERROR: "Agent 输出解析失败",
    ErrorCode.AGENT_TOOL_ERROR: "Agent 工具调用失败",
    ErrorCode.INVALID_API_KEY: "无效的 API Key，请在设置中更新",

    ErrorCode.AUTOCAD_NOT_CONNECTED: "AutoCAD 未连接，请先连接 AutoCAD",
    ErrorCode.AUTOCAD_CONNECTION_FAILED: "AutoCAD 连接失败",
    ErrorCode.AUTOCAD_DRAWING_NOT_OPEN: "AutoCAD 中没有打开的图纸",
    ErrorCode.AUTOCAD_BLOCK_NOT_FOUND: "AutoCAD 图块未找到",
    ErrorCode.AUTOCAD_ENTITY_NOT_FOUND: "AutoCAD 图元未找到",
    ErrorCode.AUTOCAD_OPERATION_FAILED: "AutoCAD 操作失败",
    ErrorCode.AUTOCAD_COM_ERROR: "AutoCAD COM 接口错误",
    ErrorCode.AUTOCAD_LAYER_ERROR: "AutoCAD 图层操作失败",

    ErrorCode.SYMBOL_NOT_FOUND: "图元符号未找到",
    ErrorCode.STANDARD_NOT_FOUND: "绘图规范未找到",
    ErrorCode.VECTOR_STORE_ERROR: "向量数据库操作失败",
    ErrorCode.EMBED_ERROR: "文本向量化失败",

    ErrorCode.RECOGNITION_FAILED: "图片识别失败",
    ErrorCode.MODEL_NOT_LOADED: "识别模型未加载",
    ErrorCode.IMAGE_INVALID: "图片格式无效",
    ErrorCode.IMAGE_TOO_LARGE: "图片文件过大",
    ErrorCode.NO_ELEMENTS_DETECTED: "未检测到任何电气元件",

    ErrorCode.DB_ERROR: "数据库操作失败",
    ErrorCode.DB_CONSTRAINT_ERROR: "数据库约束冲突",

    ErrorCode.SESSION_NOT_FOUND: "会话不存在",
    ErrorCode.SESSION_EXPIRED: "会话已过期",
}


def get_error_message(code: int) -> str:
    """获取错误码对应的中文描述"""
    return ERROR_MESSAGES.get(code, f"未知错误码: {code}")
