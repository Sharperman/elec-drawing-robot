"""
Skill 核心数据模型
兼容 agentskills.io 标准，支持 Pydantic 校验
"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── 枚举 ─────────────────────────────────────────────────

class SkillCategory(str, Enum):
    """Skill 分类"""
    INTERNAL = "internal"     # 代码内置（截图、点击等）
    EXTERNAL = "external"     # 从 YAML 加载
    AUTOGEN = "autogen"       # 自动生成


class SkillStatus(str, Enum):
    """Skill 状态"""
    ACTIVE = "active"
    DISABLED = "disabled"
    DELETED = "deleted"


# ─── 触发条件 ─────────────────────────────────────────────

class SkillTrigger(BaseModel):
    """Skill 触发条件"""
    patterns: List[str] = Field(
        default_factory=list,
        description="触发词列表，如 ['画三极断路器', '3P breaker']"
    )
    confidence_threshold: float = Field(
        default=0.8,
        ge=0.0, le=1.0,
        description="触发置信度阈值"
    )

    @field_validator("patterns")
    @classmethod
    def validate_patterns(cls, v: List[str]) -> List[str]:
        if not v:
            return v
        cleaned = [p.strip() for p in v if p.strip()]
        return cleaned


# ─── 输入参数定义 ─────────────────────────────────────────

class SkillInputProperty(BaseModel):
    """Skill 输入参数属性"""
    type: str = Field(default="string", description="参数类型")
    description: str = Field(default="", description="参数描述")
    default: Optional[Any] = Field(default=None, description="默认值")


class SkillInputSchema(BaseModel):
    """Skill 输入参数 Schema"""
    properties: Dict[str, SkillInputProperty] = Field(
        default_factory=dict,
        description="输入参数属性定义"
    )
    required: List[str] = Field(
        default_factory=list,
        description="必需参数列表"
    )


# ─── 执行步骤 ─────────────────────────────────────────────

class SkillStep(BaseModel):
    """Skill 执行步骤"""
    tool: str = Field(..., description="工具名称，如 insert_element")
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="工具参数，支持 ${inputs.x} 模板语法"
    )
    description: str = Field(default="", description="步骤描述")
    timeout_ms: int = Field(default=30000, description="步骤超时(毫秒)")

    @field_validator("tool")
    @classmethod
    def validate_tool(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("工具名称不能为空")
        return v.strip()


# ─── 执行配置 ─────────────────────────────────────────────

class SkillExecutionConfig(BaseModel):
    """Skill 执行配置"""
    type: str = Field(default="python", description="执行类型")
    entry: str = Field(default="execute.py", description="入口文件")
    steps: List[SkillStep] = Field(
        default_factory=list,
        description="执行步骤列表"
    )


# ─── 元数据 ───────────────────────────────────────────────

class SkillMetadata(BaseModel):
    """Skill 元数据 — agentskills.io 兼容"""
    api_version: str = Field(default="1.0", description="API 版本")
    spec_version: str = Field(default="1.0.0", description="规范版本")

    name: str = Field(..., description="Skill 名称，如 draw_3p_breaker")
    description: str = Field(default="", description="Skill 描述")
    author: str = Field(default="system", description="作者")
    created_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="创建时间"
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="更新时间"
    )
    version: str = Field(default="1.0.0", description="版本")


# ─── HermesSkill — 完整的 Skill 对象 ──────────────────────

class HermesSkill(BaseModel):
    """完整的 Hermes Skill"""
    skill_id: str = Field(..., description="唯一标识符")
    metadata: SkillMetadata = Field(..., description="元数据")
    category: SkillCategory = Field(
        default=SkillCategory.EXTERNAL,
        description="分类"
    )
    status: SkillStatus = Field(default=SkillStatus.ACTIVE, description="状态")
    triggers: Optional[SkillTrigger] = Field(default=None, description="触发条件")
    inputs: SkillInputSchema = Field(
        default_factory=SkillInputSchema,
        description="输入参数"
    )
    execution: SkillExecutionConfig = Field(
        ..., description="执行配置"
    )

    # 运行时统计
    use_count: int = Field(default=0, description="使用次数")
    success_count: int = Field(default=0, description="成功次数")
    last_used_at: Optional[str] = Field(default=None, description="最后使用时间")

    # 来源
    source_path: Optional[str] = Field(default=None, description="YAML 文件路径")

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.use_count == 0:
            return 1.0
        return round(self.success_count / self.use_count, 4)

    def to_dict(self) -> Dict[str, Any]:
        """转为 JSON 可序列化字典"""
        return json.loads(self.model_dump_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HermesSkill:
        """从字典创建"""
        return cls.model_validate(data)


# ─── 辅助类型 ─────────────────────────────────────────────

class SkillMatch(BaseModel):
    """Skill 匹配结果"""
    skill: HermesSkill
    match_type: str = Field(..., description="匹配方式: exact|pattern|fuzzy")
    confidence: float = Field(..., ge=0.0, le=1.0, description="匹配置信度")


class ExecutionResult(BaseModel):
    """Skill 执行结果"""
    success: bool
    outputs: List[Dict[str, Any]] = Field(default_factory=list)
    logs: List[str] = Field(default_factory=list)
    execution_time_ms: int = Field(default=0)
    error_message: Optional[str] = Field(default=None)
