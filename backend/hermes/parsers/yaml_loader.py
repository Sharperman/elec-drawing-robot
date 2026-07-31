"""
YAML Skill 加载器
从 agentskills.io 兼容的 skill.yaml 文件加载并校验 Skill
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
import yaml

from hermes.models.skill import (
    HermesSkill,
    SkillCategory,
    SkillExecutionConfig,
    SkillInputProperty,
    SkillInputSchema,
    SkillMetadata,
    SkillStatus,
    SkillStep,
    SkillTrigger,
)


class YAMLLoader:
    """
    YAML Skill 加载器
    负责解析 skill.yaml → HermesSkill 对象
    """

    REQUIRED_FIELDS = [
        "metadata.name",
        "execution.steps",
    ]

    def __init__(self, skills_dir: str):
        self._skills_dir = Path(skills_dir)
        if not self._skills_dir.exists():
            self._skills_dir.mkdir(parents=True, exist_ok=True)

    def load_all(self) -> list[HermesSkill]:
        """从 skills_dir 下所有子目录加载 Skill"""
        skills: list[HermesSkill] = []
        for entry in sorted(self._skills_dir.iterdir()):
            if entry.is_dir():
                yaml_path = entry / "skill.yaml"
                if yaml_path.exists():
                    try:
                        skill = self._load_single(yaml_path)
                        if skill:
                            skills.append(skill)
                    except Exception as e:
                        logger.warning(f"加载 Skill 失败 {yaml_path}: {e}")
        return skills

    def load(self, skill_dir: str) -> HermesSkill | None:
        """从指定目录加载单个 Skill"""
        path = Path(skill_dir)
        if path.is_dir():
            path = path / "skill.yaml"
        if not path.exists():
            logger.warning(f"Skill YAML 不存在: {path}")
            return None
        return self._load_single(path)

    def _load_single(self, yaml_path: Path) -> HermesSkill | None:
        """解析单个 skill.yaml 文件"""
        try:
            raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            logger.error(f"YAML 解析失败 {yaml_path}: {e}")
            return None

        if not isinstance(raw, dict):
            logger.error(f"YAML 内容不是字典: {yaml_path}")
            return None

        # 校验必需字段
        missing = self._check_required(raw)
        if missing:
            logger.error(f"缺失必需字段 {yaml_path}: {missing}")
            return None

        try:
            meta = raw.get("metadata", {})

            # 构建 SkillMetadata
            metadata = SkillMetadata(
                name=meta.get("name", yaml_path.parent.name),
                description=meta.get("description", ""),
                author=meta.get("author", "unknown"),
                created_at=meta.get("created_at", ""),
                updated_at=meta.get("updated_at", ""),
                version=meta.get("version", "1.0.0"),
                api_version=raw.get("api_version", "1.0"),
                spec_version=raw.get("spec_version", "1.0.0"),
            )

            # 构建 Triggers
            triggers_raw = raw.get("triggers")
            triggers: SkillTrigger | None = None
            if triggers_raw and isinstance(triggers_raw, dict):
                triggers = SkillTrigger(
                    patterns=triggers_raw.get("patterns", []),
                    confidence_threshold=triggers_raw.get(
                        "confidence_threshold", 0.8
                    ),
                )

            # 构建 InputSchema
            inputs_raw = raw.get("inputs", {})
            inputs_schema = SkillInputSchema()
            if isinstance(inputs_raw, dict) and "properties" in inputs_raw:
                props = {}
                for k, v in inputs_raw["properties"].items():
                    if isinstance(v, dict):
                        props[k] = SkillInputProperty(
                            type=v.get("type", "string"),
                            description=v.get("description", ""),
                            default=v.get("default"),
                        )
                inputs_schema = SkillInputSchema(
                    properties=props,
                    required=inputs_raw.get("required", []),
                )

            # 构建 ExecutionConfig
            exec_raw = raw.get("execution", {})
            steps = []
            for s in exec_raw.get("steps", []):
                steps.append(SkillStep(
                    tool=s.get("tool", ""),
                    params=s.get("params", {}),
                    description=s.get("description", ""),
                    timeout_ms=s.get("timeout_ms", 30000),
                ))

            execution = SkillExecutionConfig(
                type=exec_raw.get("type", "python"),
                entry=exec_raw.get("entry", "execute.py"),
                steps=steps,
            )

            skill_id = meta.get("name", yaml_path.parent.name)

            skill = HermesSkill(
                skill_id=skill_id,
                metadata=metadata,
                category=SkillCategory.EXTERNAL,
                status=SkillStatus.ACTIVE,
                triggers=triggers,
                inputs=inputs_schema,
                execution=execution,
                source_path=str(yaml_path.absolute()),
            )

            logger.debug(f"Loaded Skill: {skill_id} ({len(steps)} steps)")
            return skill

        except Exception as e:
            logger.error(f"Skill 构建失败 {yaml_path}: {e}")
            return None

    def save(self, skill: HermesSkill, yaml_path: Path | None = None) -> Path:
        """将 Skill 保存为 YAML 文件"""
        if yaml_path is None:
            yaml_path = self._skills_dir / skill.skill_id / "skill.yaml"
        yaml_path.parent.mkdir(parents=True, exist_ok=True)

        raw = {
            "api_version": skill.metadata.api_version,
            "spec_version": skill.metadata.spec_version,
            "metadata": {
                "name": skill.metadata.name,
                "description": skill.metadata.description,
                "author": skill.metadata.author,
                "created_at": skill.metadata.created_at,
                "updated_at": skill.metadata.updated_at,
                "version": skill.metadata.version,
            },
        }

        if skill.triggers:
            raw["triggers"] = {
                "patterns": skill.triggers.patterns,
                "confidence_threshold": skill.triggers.confidence_threshold,
            }

        raw["inputs"] = {
            "properties": {
                k: {
                    "type": v.type,
                    "description": v.description,
                    "default": v.default,
                }
                for k, v in skill.inputs.properties.items()
            },
            "required": skill.inputs.required,
        }

        raw["execution"] = {
            "type": skill.execution.type,
            "entry": skill.execution.entry,
            "steps": [
                {
                    "tool": step.tool,
                    "params": step.params,
                    "description": step.description,
                    "timeout_ms": step.timeout_ms,
                }
                for step in skill.execution.steps
            ],
        }

        yaml_path.write_text(
            yaml.dump(raw, default_flow_style=False, allow_unicode=True,
                      sort_keys=False, indent=2),
            encoding="utf-8",
        )

        logger.info(f"Skill 已保存: {yaml_path}")
        return yaml_path

    def _check_required(self, data: dict[str, Any]) -> list[str]:
        """检查必需字段"""
        missing = []
        for field in self.REQUIRED_FIELDS:
            parts = field.split(".")
            current = data
            for part in parts:
                if isinstance(current, dict):
                    current = current.get(part)
                else:
                    current = None
                    break
            if not current:
                missing.append(field)
        return missing
