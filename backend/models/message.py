"""
ChatMessage 模型（与 drawing_session.py 分离的单独模块）
重新导出，避免循环引用
"""
# ChatMessage 已定义在 drawing_session.py 中
# 此模块仅用于兼容性导出
from models.drawing_session import ChatMessage

__all__ = ["ChatMessage"]
