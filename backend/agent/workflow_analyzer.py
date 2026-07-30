"""
工作流分析器
录制结束后，手动触发 LLM 分析操作序列，生成 WorkflowPattern。
"""
import json
import threading
from pathlib import Path
from typing import Optional

from loguru import logger


class WorkflowAnalyzer:
    """分析录制内容 → 生成 DrawingPattern"""

    ANALYZE_PROMPT = """你是一位资深电气工程师。以下是某位工程师操作 AutoCAD 绘制电气图纸的完整操作记录。

请分析操作序列，提取以下信息：
1. **绘图顺序**: 先画什么，后画什么，中间的调整逻辑
2. **设备使用**: 使用了哪些设备类型，数量，典型位置
3. **标注风格**: 标注位置（左上/右上/居中），字体大小偏好，前缀规则
4. **布局规律**: 设备间距，对齐方式，分层/分区习惯
5. **连接模式**: 设备间连线顺序，线型选择
6. **修改模式**: 哪些步骤被反复调整（说明用户的纠错习惯）
7. **最佳实践**: 从操作序列中总结出可复用的工作流程

操作时间线:
{steps_text}

请输出 JSON DrawingPattern 格式:
{{
  "name": "工作流名称",
  "description": "不少于100字的完整描述",
  "topology": {{}},
  "devices": [],
  "layout_rules": [],
  "annotation_style": {{}},
  "connection_patterns": [],
  "layer_spec": {{}},
  "workflow_steps": ["步骤1: ...", "步骤2: ..."]
}}
"""

    def __init__(self):
        self._analyzing: dict = {}  # {session_id: True}

    def analyze(self, session_id: int) -> dict:
        """
        分析指定录制会话。
        返回 {"pattern_id": int, "summary": dict} 或 {"error": str}
        """
        from models.session import get_session_local

        db = get_session_local()()
        try:
            from models.operation_session import OperationSession, OperationStep

            session = db.query(OperationSession).filter_by(id=session_id).first()
            if not session:
                return {"error": "录制不存在"}

            steps = db.query(OperationStep).filter_by(session_id=session_id).order_by(OperationStep.seq).all()

            if not steps:
                return {"error": "无操作步骤"}

            # 构建时间线文本
            steps_text_parts = []
            for s in steps:
                ts = s.timestamp or 0
                minutes = int(ts // 60)
                seconds = int(ts % 60)
                desc = s.description or "未知操作"
                steps_text_parts.append(f"[{minutes:02d}:{seconds:02d}] {desc}")

            steps_text = "\n".join(steps_text_parts)

            # 调用 LLM 分析
            try:
                from agent.llm_factory import create_primary_llm
                from langchain_core.messages import HumanMessage

                llm = create_primary_llm(db=db)
                prompt = self.ANALYZE_PROMPT.format(steps_text=steps_text[:8000])
                resp = llm.invoke([HumanMessage(content=prompt)])
                content = resp.content if hasattr(resp, "content") else str(resp)

                # 解析 JSON
                from agent.learn_agent import LearnAgent  # 复用 _parse_json
                # 临时创建 agent 实例以使用 _parse_json
                agent = LearnAgent.__new__(LearnAgent)
                parsed = agent._parse_json(content)

                if parsed and isinstance(parsed, dict) and "error" not in str(parsed.get("raw", "")):
                    # 保存为 DrawingPattern
                    from models.drawing_pattern import DrawingPattern
                    dp_name = parsed.get("name", f"录制分析_{session_id}")

                    # 检查是否已有同名 Pattern
                    existing = db.query(DrawingPattern).filter_by(name=dp_name, source_type="recording").first()
                    if existing:
                        dp = existing
                    else:
                        dp = DrawingPattern(name=dp_name, source_type="recording")

                    dp.description = parsed.get("description", "")
                    # 合并拓扑/设备等字段
                    import json as _json
                    for key in ("topology", "devices", "layout_rules", "annotation_style",
                                "connection_patterns", "layer_spec"):
                        if key in parsed and parsed[key]:
                            setattr(dp, key, _json.dumps(parsed[key], ensure_ascii=False) if isinstance(parsed[key], (dict, list)) else str(parsed[key]))

                    dp.is_active = True
                    db.add(dp)
                    db.commit()
                    db.refresh(dp)

                    return {"pattern_id": dp.id, "summary": parsed.get("description", "")[:200]}

                return {"error": "LLM 分析结果不可用"}

            except Exception as e:
                logger.error(f"LLM 分析失败: {e}")
                return {"error": str(e)[:200]}

        except Exception as e:
            logger.error(f"分析失败: {e}")
            return {"error": str(e)[:200]}
        finally:
            db.close()


workflow_analyzer = WorkflowAnalyzer()
