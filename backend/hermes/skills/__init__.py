"""
Hermes Skill 基类

所有 Hermes 工具都继承此类，实现标准接口：
- name / description — 供 LLM 理解
- execute(args) — 执行逻辑
- as_tool() — 转换为 LangChain Tool
"""
from abc import ABC, abstractmethod
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field


class HermesSkillInput(BaseModel):
    """通用 Skill 输入 — 各 skill 可覆盖 args_schema"""
    pass


class HermesSkill(ABC):
    """Hermes Skill 抽象基类"""

    # 子类必须定义
    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """执行 Skill，返回人类可读结果字符串"""
        pass

    def as_tool(self) -> BaseTool:
        """将 Skill 包装为 LangChain Tool"""
        skill = self

        class _Tool(BaseTool):
            name: str = skill.name
            description: str = skill.description
            args_schema: Type[BaseModel] = HermesSkillInput

            def _run(self, **kwargs) -> str:
                # 状态追踪
                from hermes import hermes_state
                hermes_state.set_status(f"执行: {skill.name}({str(kwargs)[:60]})")
                hermes_state.inc_action()
                try:
                    return skill.execute(**kwargs)
                except Exception as e:
                    return f"[{skill.name}_ERR] {e}"

        tool = _Tool()
        return tool


def make_skill(name: str, description: str, input_schema: Type[BaseModel], execute_fn) -> HermesSkill:
    """
    快捷创建 Skill 的工厂函数。
    用于外部模块快速注册自定义 Skill，无需定义完整类。
    """
    class _DynamicSkill(HermesSkill):
        name = name
        description = description

        def execute(self, **kwargs):
            return execute_fn(**kwargs)

        def as_tool(self) -> BaseTool:
            skill = self

            class _Tool(BaseTool):
                name: str = skill.name
                description: str = skill.description
                args_schema: Type[BaseModel] = input_schema

                def _run(self, **kwargs) -> str:
                    from hermes import hermes_state
                    hermes_state.set_status(f"执行: {skill.name}({str(kwargs)[:60]})")
                    hermes_state.inc_action()
                    try:
                        return skill.execute(**kwargs)
                    except Exception as e:
                        return f"[{skill.name}_ERR] {e}"

            return _Tool()

    return _DynamicSkill()
