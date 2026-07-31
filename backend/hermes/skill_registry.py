"""
Skill Registry — Skill 注册表
管理所有 Skill 的注册、查找、匹配
"""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from hermes.models.skill import (
    HermesSkill,
    SkillCategory,
    SkillMatch,
    SkillStatus,
)
from hermes.parsers.yaml_loader import YAMLLoader


class SkillRegistry:
    """
    Skill 注册表

    三类 Skill:
    1. Internal: 代码内置，运行时注册
    2. External: 从 YAML 文件加载
    3. AutoGen: 自动生成的 Skill
    """

    def __init__(self, skills_dir: str):
        self._skills_dir = Path(skills_dir)
        self._internal: dict[str, HermesSkill] = {}
        self._external: dict[str, HermesSkill] = {}
        self._autogen: dict[str, HermesSkill] = {}

        self._yaml_loader = YAMLLoader(str(self._skills_dir))

        # 运行时执行映射：skill_id → callable
        self._executors: dict[str, Callable] = {}

    # ─── 注册 ────────────────────────────────────────────

    def register_internal(
        self,
        skill: HermesSkill,
        executor: Callable | None = None,
    ) -> None:
        """注册内置 Skill（截图、点击等）"""
        skill.category = SkillCategory.INTERNAL
        self._internal[skill.skill_id] = skill
        if executor:
            self._executors[skill.skill_id] = executor
        logger.debug(f"Internal Skill 已注册: {skill.skill_id}")

    def register_external(self, skill: HermesSkill) -> None:
        """注册外部 Skill（从 YAML 加载）"""
        self._external[skill.skill_id] = skill
        logger.debug(f"External Skill 已注册: {skill.skill_id}")

    def register_autogen(self, skill: HermesSkill) -> None:
        """注册自动生成的 Skill"""
        skill.category = SkillCategory.AUTOGEN
        self._autogen[skill.skill_id] = skill
        logger.info(f"AutoGen Skill 已注册: {skill.skill_id}")

    def register_executor(
        self, skill_id: str, executor: Callable
    ) -> None:
        """注册 Skill 的执行函数"""
        self._executors[skill_id] = executor

    def unregister(self, skill_id: str) -> bool:
        """注销 Skill"""
        for registry in [self._internal, self._external, self._autogen]:
            if skill_id in registry:
                del registry[skill_id]
                self._executors.pop(skill_id, None)
                logger.info(f"Skill 已注销: {skill_id}")
                return True
        return False

    # ─── 加载 ────────────────────────────────────────────

    def load_external_skills(self) -> int:
        """从 YAML 目录加载所有外部 Skill"""
        skills = self._yaml_loader.load_all()
        count = 0
        for skill in skills:
            if skill.skill_id not in self._external:
                self.register_external(skill)
                count += 1
        logger.info(f"已加载 {count} 个外部 Skill")
        return count

    def load_autogen_skills(self, skills: list[HermesSkill]) -> int:
        """批量注册自动生成的 Skill"""
        count = 0
        for skill in skills:
            if skill.skill_id not in self._autogen:
                self.register_autogen(skill)
                count += 1
        return count

    # ─── 查询 ────────────────────────────────────────────

    def get(self, skill_id: str) -> HermesSkill | None:
        """按 ID 获取 Skill"""
        for registry in [self._internal, self._external, self._autogen]:
            if skill_id in registry:
                return registry[skill_id]
        return None

    def get_by_category(
        self, category: SkillCategory
    ) -> list[HermesSkill]:
        """按分类获取"""
        if category == SkillCategory.INTERNAL:
            return list(self._internal.values())
        elif category == SkillCategory.EXTERNAL:
            return list(self._external.values())
        elif category == SkillCategory.AUTOGEN:
            return list(self._autogen.values())
        return []

    def get_all(self, include_disabled: bool = False) -> list[HermesSkill]:
        """获取所有可用 Skill"""
        skills: list[HermesSkill] = []
        for registry in [self._internal, self._external, self._autogen]:
            for skill in registry.values():
                if include_disabled or skill.status == SkillStatus.ACTIVE:
                    skills.append(skill)
        # 按分类和名称排序
        skills.sort(key=lambda s: (s.category.value, s.skill_id))
        return skills

    def count(self) -> dict[str, int]:
        """分类统计"""
        return {
            "internal": len(self._internal),
            "external": len(self._external),
            "autogen": len(self._autogen),
            "total": (len(self._internal) + len(self._external)
                      + len(self._autogen)),
        }

    def get_executor(self, skill_id: str) -> Callable | None:
        """获取 Skill 的执行函数"""
        return self._executors.get(skill_id)

    # ─── 匹配 ────────────────────────────────────────────

    def find_matching(self, query: str, top_k: int = 5) -> list[SkillMatch]:
        """根据用户输入匹配最适合的 Skill"""
        query = query.strip().lower()
        if not query:
            return []

        matches: list[SkillMatch] = []
        all_skills = self.get_all()

        for skill in all_skills:
            # 1. 精确匹配
            if query == skill.skill_id.lower():
                matches.append(SkillMatch(
                    skill=skill, match_type="exact", confidence=1.0
                ))
                continue

            if skill.metadata and query == skill.metadata.name.lower():
                matches.append(SkillMatch(
                    skill=skill, match_type="exact", confidence=1.0
                ))
                continue

            # 2. 触发词匹配
            if skill.triggers and skill.triggers.patterns:
                for pattern in skill.triggers.patterns:
                    pattern_lower = pattern.lower()
                    if query == pattern_lower:
                        matches.append(SkillMatch(
                            skill=skill, match_type="pattern",
                            confidence=skill.triggers.confidence_threshold
                        ))
                        break
                    elif (len(query) > 2
                          and pattern_lower in query):
                        matches.append(SkillMatch(
                            skill=skill, match_type="fuzzy",
                            confidence=skill.triggers.confidence_threshold * 0.8
                        ))
                        break

            # 3. 描述匹配（关键词）
            if skill.metadata and skill.metadata.description:
                desc = skill.metadata.description.lower()
                query_keywords = set(query.split())
                match_keywords = query_keywords & set(desc.split())
                if len(match_keywords) >= 2:
                    confidence = min(0.7, 0.3 + 0.1 * len(match_keywords))
                    matches.append(SkillMatch(
                        skill=skill, match_type="fuzzy",
                        confidence=confidence
                    ))

        # 按置信度排序
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches[:top_k]

    # ─── 工具映射 ────────────────────────────────────────

    def to_langchain_tools(self) -> list[Any]:
        """将 Hermes Skill 转为 LangChain Tool（供 DrawAgent 使用）"""
        from langchain_core.tools import tool as lc_tool

        tools = []
        for skill in self.get_all():
            if skill.status != SkillStatus.ACTIVE:
                continue

            @lc_tool
            def make_func(s: HermesSkill = skill):
                async def _run(**kwargs: Any) -> str:
                    """执行 Skill，返回执行结果"""
                    from hermes.skill_executor import SkillExecutor
                    executor_ = SkillExecutor()
                    result = await executor_.execute(
                        s, kwargs
                    )
                    if result.success:
                        return (
                            f"✅ Skill '{s.skill_id}' 执行成功: "
                            f"{result.outputs}"
                        )
                    else:
                        return (
                            f"❌ Skill '{s.skill_id}' 执行失败: "
                            f"{result.error_message}"
                        )
                return _run

            func = make_func(skill)
            func.__name__ = f"hermes_{skill.skill_id}"
            func.__doc__ = (
                f"Hermes Skill: {skill.metadata.description}"
                if skill.metadata else ""
            )

            tools.append(func)

        return tools

    def to_slash_commands(self) -> dict[str, dict[str, Any]]:
        """生成斜杠命令配置"""
        commands = {}
        for skill in self.get_all():
            if skill.status != SkillStatus.ACTIVE:
                continue
            name = skill.skill_id.replace("_", "-")
            commands[f"/{name}"] = {
                "skill_id": skill.skill_id,
                "description": (
                    skill.metadata.description if skill.metadata else ""
                ),
                "trigger_patterns": (
                    skill.triggers.patterns if skill.triggers else []
                ),
            }

        # 添加通用命令
        commands["/hermes"] = {
            "skill_id": None,
            "description": "桌面操作（CU 模式下可用）",
            "trigger_patterns": [],
        }

        return commands

    # ─── 持久化 ────────────────────────────────────────────

    def save_autogen_skill(self, skill: HermesSkill) -> Path:
        """保存自动生成的 Skill 到文件"""
        autogen_dir = self._skills_dir / "autogen"
        return self._yaml_loader.save(
            skill,
            autogen_dir / skill.skill_id / "skill.yaml",
        )

    def delete_autogen_skill(self, skill_id: str) -> bool:
        """删除自动生成的 Skill 文件"""
        autogen_dir = self._skills_dir / "autogen"
        yaml_path = autogen_dir / skill_id / "skill.yaml"
        if yaml_path.exists():
            yaml_path.unlink()
            # 尝试删除空目录
            yaml_path.parent.rmdir() if yaml_path.parent.exists() else None
            return True
        return False
