"""
电气规范知识库
================

结构化的电气专业知识和本体规范，用于图纸审查。

数据来源（摘要自）：
- GB 50059  35~110kV 变电所设计规范
- GB 50060  3~110kV 高压配电装置设计规范
- GB 50053  20kV 及以下变电所设计规范
- GB 50054  低压配电设计规范
- GB 50217  电力工程电缆设计标准
- GB 50065  交流电气装置的接地设计规范
- GB 50062  电力装置的继电保护和自动装置设计规范
- NB/T 31105  海上风电场工程电气设计规范
- NB/T 31051  风电机组高电压穿越能力测试规程
- GB/T 4728  电气简图用图形符号 (等同 IEC 60617)
- DL/T 5352  高压配电装置设计技术规程

每个审查规则包含：
- rule_id: 规则编号
- category: 分类 (完整性/规范性/一致性/安全性)
- title: 规则标题
- description: 规则描述
- severity: 严重程度 (error/warning/info)
- check_items: 检查项列表
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CheckItem:
    """审查检查项"""
    item: str
    detail: str = ""
    expected: str = ""


@dataclass
class CheckRule:
    """审查规则"""
    rule_id: str
    category: str  # 完整性/规范性/一致性/安全性
    title: str
    description: str
    severity: str  # error/warning/info
    gb_ref: str  # 引用标准
    check_items: list[CheckItem] = field(default_factory=list)


# ============================================================
# 审查规则库
# ============================================================

CHECK_RULES: list[CheckRule] = [
    # ── 完整性检查 ──
    CheckRule(
        rule_id="CMP-001",
        category="完整性",
        title="图纸标题栏完整性",
        description="图纸必须包含完整的标题栏信息：项目名称、图纸名称、图号、比例、设计/审核/批准人员",
        severity="error",
        gb_ref="GB/T 14689 技术制图 图纸幅面和格式",
        check_items=[
            CheckItem("项目名称", "标题栏中是否标注项目名称"),
            CheckItem("图纸名称", "标题栏中是否标注图纸名称（如：电气主接线图）"),
            CheckItem("图号", "标题栏中是否有唯一图号"),
            CheckItem("比例", "是否标注绘图比例"),
            CheckItem("设计/制图/审核", "是否有设计、制图、审核签署栏"),
        ],
    ),
    CheckRule(
        rule_id="CMP-002",
        category="完整性",
        title="设备编号完整性",
        description="所有主要电气设备必须有唯一编号标识，编号规则应符合企业标准",
        severity="error",
        gb_ref="GB 50059 第3.1节",
        check_items=[
            CheckItem("断路器编号", "每个断路器应有编号（如 QF1, QF2）"),
            CheckItem("隔离开关编号", "每个隔离开关应有编号（如 QS1, QS2）"),
            CheckItem("变压器编号", "每台变压器应有编号（如 T1, T2, 1#主变）"),
            CheckItem("母线编号", "每段母线应有标识（如 10kV I 段母线）"),
            CheckItem("互感器编号", "电压/电流互感器应有编号（如 TV1, TA1）"),
        ],
    ),
    CheckRule(
        rule_id="CMP-003",
        category="完整性",
        title="图例与说明完整性",
        description="图纸应包含图例说明表，列出所有使用的图形符号及其含义",
        severity="warning",
        gb_ref="GB/T 4728 电气简图用图形符号",
        check_items=[
            CheckItem("图例表", "是否包含图例/符号说明表"),
            CheckItem("符号标准", "图例符号是否符合 GB/T 4728 (IEC 60617)"),
            CheckItem("特殊符号说明", "非标准符号是否有文字说明"),
        ],
    ),
    CheckRule(
        rule_id="CMP-004",
        category="完整性",
        title="技术参数标注完整性",
        description="主要设备应标注关键技术参数",
        severity="warning",
        gb_ref="GB 50059 第4章",
        check_items=[
            CheckItem("变压器参数", "容量(kVA/MVA)、电压比、连接组别、阻抗电压"),
            CheckItem("断路器参数", "额定电压、额定电流、额定开断电流"),
            CheckItem("电缆参数", "型号、截面、电压等级"),
            CheckItem("母线参数", "材质、规格、额定电流"),
            CheckItem("电压等级标注", "各级电压应在母线或设备旁明确标注"),
        ],
    ),

    # ── 规范性检查 ──
    CheckRule(
        rule_id="STD-001",
        category="规范性",
        title="电压等级标注规范",
        description="电压等级标注应符合行业惯例，使用 kV 为单位，标准电压等级应符合 GB/T 156",
        severity="warning",
        gb_ref="GB/T 156 标准电压",
        check_items=[
            CheckItem("电压单位", "电压标注应使用 kV 为单位"),
            CheckItem("标准电压等级", "应使用标准电压等级：0.4/10/20/35/66/110/220/330/500 kV"),
            CheckItem("电压比标注", "变压器应标注电压比，如 110/10.5 kV"),
        ],
    ),
    CheckRule(
        rule_id="STD-002",
        category="规范性",
        title="电气符号使用规范",
        description="电气图形符号应符合 GB/T 4728 (IEC 60617) 标准",
        severity="error",
        gb_ref="GB/T 4728 / IEC 60617",
        check_items=[
            CheckItem("符号标准化", "所有电气符号应来自标准符号库"),
            CheckItem("符号方向", "符号方向应符合标准（如断路器开口方向）"),
            CheckItem("符号比例", "同一图纸内同类符号大小应一致"),
        ],
    ),
    CheckRule(
        rule_id="STD-003",
        category="规范性",
        title="图层命名规范",
        description="图层命名应符合企业或行业 CAD 标准，便于图纸管理和协作",
        severity="info",
        gb_ref="GB/T 18229 CAD工程制图规则",
        check_items=[
            CheckItem("图层命名", "图层名应有意义，如 ELEC-PRIMARY, ELEC-SECONDARY"),
            CheckItem("图层颜色", "不同电压等级/功能应使用不同颜色区分"),
            CheckItem("图层线型", "不同功能应使用合适线型（实线/虚线/点划线）"),
        ],
    ),
    CheckRule(
        rule_id="STD-004",
        category="规范性",
        title="文字标注规范",
        description="文字样式、高度、对齐方式应符合制图规范",
        severity="info",
        gb_ref="GB/T 14691 技术制图 字体",
        check_items=[
            CheckItem("文字高度", "一般标注文字高度 3.5mm，标题 5-7mm"),
            CheckItem("文字字体", "应使用工程字字体（如 gbcbig.shx）"),
            CheckItem("文字方向", "文字方向应与读图方向一致（从左到右）"),
        ],
    ),

    # ── 一致性检查 ──
    CheckRule(
        rule_id="CNS-001",
        category="一致性",
        title="设备编号一致性",
        description="同一设备在不同图纸或同一图纸不同位置的编号必须一致",
        severity="error",
        gb_ref="GB 50059 第3章",
        check_items=[
            CheckItem("编号唯一性", "同一编号不应出现在两个不同设备上"),
            CheckItem("编号连续性", "编号应连续，避免跳号（如 QF1, QF2, QF5）"),
            CheckItem("编号格式一致", "同类设备编号格式应统一（如都用 QF 前缀）"),
        ],
    ),
    CheckRule(
        rule_id="CNS-002",
        category="一致性",
        title="主接线拓扑一致性",
        description="主接线图中设备的连接关系应逻辑自洽，符合电气原理",
        severity="error",
        gb_ref="GB 50059 第3.2节",
        check_items=[
            CheckItem("电源进线", "电源进线数量与标注一致"),
            CheckItem("母线分段", "母线分段方式与标注一致"),
            CheckItem("变压器连接", "变压器高低压侧连接方式正确"),
            CheckItem("保护配置", "断路器与保护装置配置对应"),
        ],
    ),
    CheckRule(
        rule_id="CNS-003",
        category="一致性",
        title="参数一致性",
        description="设备标注的技术参数应与系统参数匹配",
        severity="warning",
        gb_ref="GB 50059 第4章",
        check_items=[
            CheckItem("电压匹配", "设备额定电压 >= 系统标称电压"),
            CheckItem("容量匹配", "变压器容量与负荷匹配"),
            CheckItem("短路电流匹配", "断路器开断能力 >= 短路电流"),
        ],
    ),

    # ── 安全性检查 ──
    CheckRule(
        rule_id="SAF-001",
        category="安全性",
        title="接地系统完整性",
        description="电气主接线图中应体现完整的接地系统设计",
        severity="error",
        gb_ref="GB 50065 交流电气装置的接地设计规范",
        check_items=[
            CheckItem("接地符号", "中性点、设备外壳应有接地符号"),
            CheckItem("接地母线", "应有接地母线或接地网示意"),
            CheckItem("避雷器配置", "进出线、母线应有避雷器保护"),
            CheckItem("接地电阻", "应有接地电阻要求标注"),
        ],
    ),
    CheckRule(
        rule_id="SAF-002",
        category="安全性",
        title="保护配置完整性",
        description="主要设备和线路应配置相应的继电保护装置",
        severity="error",
        gb_ref="GB 50062 电力装置的继电保护和自动装置设计规范",
        check_items=[
            CheckItem("变压器保护", "主变应有差动保护、瓦斯保护、过流保护"),
            CheckItem("母线保护", "重要母线应有母线差动保护"),
            CheckItem("线路保护", "进出线应有过流/距离/差动保护"),
            CheckItem("断路器失灵保护", "220kV及以上应有断路器失灵保护"),
        ],
    ),
    CheckRule(
        rule_id="SAF-003",
        category="安全性",
        title="安全净距检查",
        description="带电部分之间及带电部分对接地部分的安全净距应符合规范",
        severity="error",
        gb_ref="GB 50060 高压配电装置设计规范 表5.1.1",
        check_items=[
            CheckItem("相间距离", "不同电压等级应有对应的相间安全距离"),
            CheckItem("对地距离", "带电部分对地距离满足要求"),
            CheckItem("检修通道", "配电装置应有足够的检修通道"),
        ],
    ),

    # ── 海上风电专项检查 ──
    CheckRule(
        rule_id="OSW-001",
        category="完整性",
        title="海上风电 - 海缆标注",
        description="海上风电项目应标注海缆型号、截面、长度、敷设方式",
        severity="error",
        gb_ref="NB/T 31105 海上风电场工程电气设计规范",
        check_items=[
            CheckItem("海缆型号", "是否标注海底电缆型号（如 HYJQF41）"),
            CheckItem("海缆截面", "是否标注导体截面"),
            CheckItem("海缆长度", "是否标注海缆路由长度"),
            CheckItem("海缆电压", "是否标注海缆额定电压等级"),
        ],
    ),
    CheckRule(
        rule_id="OSW-002",
        category="安全性",
        title="海上风电 - 升压站配置",
        description="海上升压站/陆上集控中心的主接线应满足 N-1 准则",
        severity="warning",
        gb_ref="NB/T 31105 第6章",
        check_items=[
            CheckItem("主变冗余", "主变压器是否满足 N-1（至少2台或留有备用）"),
            CheckItem("GIS配置", "220kV及以上是否采用 GIS"),
            CheckItem("无功补偿", "是否配置无功补偿装置"),
            CheckItem("应急电源", "是否配置应急/备用电源"),
        ],
    ),
    CheckRule(
        rule_id="OSW-003",
        category="一致性",
        title="海上风电 - 风机汇集系统",
        description="风机汇流接线方式应与风机数量、单机容量匹配",
        severity="warning",
        gb_ref="NB/T 31105 第5章",
        check_items=[
            CheckItem("汇流方式", "是否明确风机汇流方式（链式/环形/星形）"),
            CheckItem("回路容量", "每回集电线路接入风机数量是否合理（通常4-8台）"),
            CheckItem("电压等级", "集电线路电压等级是否合理（通常 35kV 或 66kV）"),
        ],
    ),

    # ── 设计合理性 ──
    CheckRule(
        rule_id="DSN-001",
        category="完整性",
        title="母线接线方式合理性",
        description="根据电压等级和重要性，母线接线方式应满足可靠性要求",
        severity="info",
        gb_ref="GB 50059 第3.2节",
        check_items=[
            CheckItem("110kV及以上", "应采用双母线或单母线分段接线"),
            CheckItem("35-66kV", "可采用单母线分段或双母线"),
            CheckItem("10kV", "可采用单母线分段"),
            CheckItem("0.4kV", "可采用单母线"),
        ],
    ),
    CheckRule(
        rule_id="DSN-002",
        category="规范性",
        title="计量与测量配置",
        description="应配置必要的电压、电流互感器用于计量和测量",
        severity="warning",
        gb_ref="GB 50059 第6章",
        check_items=[
            CheckItem("计量PT/CT", "贸易结算点应有计量用 PT/CT"),
            CheckItem("测量PT/CT", "各回路应有测量用 CT"),
            CheckItem("母线PT", "各电压等级母线应有母线 PT"),
        ],
    ),
]


# ============================================================
# 规范上下文构建
# ============================================================

class ElectricalStandards:
    """电气规范知识库"""

    @staticmethod
    def get_check_rules() -> list[CheckRule]:
        """获取所有审查规则"""
        return CHECK_RULES

    @staticmethod
    def get_rules_by_category(category: str) -> list[CheckRule]:
        """按分类获取规则"""
        return [r for r in CHECK_RULES if r.category == category]

    @staticmethod
    def get_rules_by_severity(severity: str) -> list[CheckRule]:
        """按严重程度获取规则"""
        return [r for r in CHECK_RULES if r.severity == severity]

    @staticmethod
    def format_checklist() -> str:
        """格式化为审查清单（注入 Agent Prompt）"""
        lines = ["## 电气图纸审查清单", ""]
        
        categories: dict[str, list[CheckRule]] = {}
        for rule in CHECK_RULES:
            categories.setdefault(rule.category, []).append(rule)

        for cat, rules in categories.items():
            lines.append(f"### {cat}检查")
            lines.append("")
            for r in rules:
                severity_icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}.get(r.severity, "⚪")
                lines.append(f"**{severity_icon} [{r.rule_id}] {r.title}** (引用: {r.gb_ref})")
                lines.append(f"> {r.description}")
                lines.append("")
                for item in r.check_items:
                    lines.append(f"  - [ ] {item.item}: {item.detail}")
                lines.append("")
        
        return "\n".join(lines)

    @staticmethod
    def build_review_context(query: str = "") -> str:
        """
        构建注入 Agent 的审查上下文
        
        Args:
            query: 用户查询（可用于规则筛选，当前版本返回全部规则）
            
        Returns:
            格式化的规范上下文字符串
        """
        parts = []
        
        parts.append("## 电气规范知识库（图纸审查参考）")
        parts.append("")
        parts.append("以下为电气图纸审查应遵循的主要规范和检查要点：")
        parts.append("")
        
        # 列出引用的标准
        parts.append("### 引用标准")
        refs = sorted(set(r.gb_ref for r in CHECK_RULES))
        for ref in refs:
            parts.append(f"- {ref}")
        parts.append("")
        
        # 审查清单
        parts.append(ElectricalStandards.format_checklist())
        
        parts.append("---")
        parts.append("**审查说明**: 请基于上述审查清单，结合从图纸中提取的实际信息，逐项检查并给出审查结论。")
        parts.append("对于每项检查，应明确给出：✅通过 / ⚠️需改进 / ❌不通过 / —不适用")
        parts.append("")
        
        return "\n".join(parts)


# ============================================================
# 全局单例
# ============================================================

electrical_standards = ElectricalStandards()
