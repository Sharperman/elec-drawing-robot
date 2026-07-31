"""
视觉化图纸阅读器
通过截图 + 多模态 LLM 理解图纸内容，弥补 COM API 对非标准图纸的识别盲区
"""
import json

from loguru import logger


class VisualReader:
    """
    视觉化图纸阅读器

    流程：
    1. 截取 AutoCAD 当前视口截图
    2. 将截图 base64 发给多模态 LLM
    3. LLM 返回结构化的图纸理解结果（设备、文字、连接关系）
    """

    # 视觉分析 Prompt
    ANALYSIS_PROMPT = """你是一位资深电气工程师，正在审阅一张电气图纸的截图。

请仔细观察截图，识别并列出图纸中所有的：

## 1. 电气设备/元件
- 识别断路器、隔离开关、变压器、母线、互感器、避雷器、熔断器、接触器、电动机、发电机、电缆、接地符号等
- 对于每个设备，描述：类型、大致位置（左上/中部/右下等）、是否有设备编号标注（如 QF1、T1 等）

## 2. 文字标注
- 列出图中所有可见的文字标注
- 特别关注：设备编号（如 QF1, QF2, KM1）、电压等级（如 10kV, 0.4kV）、电缆规格、技术参数

## 3. 连接关系
- 描述设备之间的电气连接关系（母线→断路器→电缆→变压器 等）
- 判断可能的接线方式（单母线、双母线、环形等）

## 4. 图纸整体判断
- 这是什么类型的电气图纸？（主接线图、二次接线图、配电系统图、控制回路图等）
- 图纸是否完整、规范？
- 有哪些明显的问题或异常？

请以 JSON 格式输出：
{
  "devices": [
    {"type": "断路器", "label": "QF1", "position": "左上区域", "count": 1}
  ],
  "texts": [
    {"content": "10kV", "position": "顶部", "context": "电压等级标注"}
  ],
  "connections": [
    {"from": "母线", "to": "断路器QF1", "via": "电缆/导线", "description": "10kV母线经断路器引出"}
  ],
  "overview": {
    "drawing_type": "主接线图",
    "voltage_level": "10kV",
    "completeness": "完整",
    "issues": ["缺少接地符号", "部分标注模糊"]
  }
}

注意：
- 如果图纸内容很少或空白，如实描述
- 如果某类元素不存在，返回空数组
- 不要编造不存在的元素
- 用中文描述"""

    def __init__(self) -> None:
        self._snapshot = None

    @property
    def snapshot(self):
        """懒加载 AutoCADSnapshot"""
        if self._snapshot is None:
            from autocad.snapshot import autocad_snapshot
            self._snapshot = autocad_snapshot
        return self._snapshot

    def read(self, mode: str = "auto") -> dict:
        """
        视觉阅读图纸

        Args:
            mode:
                - "auto": 自动选择最佳方案（优先 DXF 文本 → 回退 SVG 多模态 → 回退 PNG 多模态）
                - "text": 纯文本模式，DXF 直接提取结构化文本（最快，无需多模态 LLM）
                - "vision": 强制视觉模式（SVG/PNG + 多模态 LLM）

        Returns:
            {
                "success": bool,
                "visual_analysis": dict,     # LLM 返回的结构化结果
                "snapshot_base64": str,      # 图片 base64（矢量 SVG 或光栅 PNG）
                "snapshot_format": "svg" | "png" | "text",  # 格式
                "dxf_text": str,             # DXF 文本提取结果（text 模式）
                "error": str | None,
            }
        """
        result = {
            "success": False,
            "visual_analysis": {},
            "snapshot_base64": "",
            "snapshot_format": "png",
            "dxf_text": "",
            "error": None,
        }

        try:
            # ── 纯文本模式：DXF 直接提取 ──
            if mode in ("auto", "text"):
                try:
                    logger.info("VisualReader: extracting DXF text...")
                    from autocad.dxf_text_extractor import dxf_text_extractor

                    dxf_text = dxf_text_extractor.extract()
                    result["dxf_text"] = dxf_text
                    result["snapshot_format"] = "text"

                    if mode == "text":
                        # 纯文本模式：直接把 DXF 文本给 LLM 分析
                        logger.info("VisualReader: calling LLM with DXF text...")
                        analysis = self._call_text_llm(dxf_text)
                        result["visual_analysis"] = analysis
                        result["success"] = True
                        logger.info("VisualReader: text analysis complete")
                        return result
                    else:
                        # auto 模式：DXF 文本提取成功，也用文本模式分析
                        logger.info("VisualReader: DXF text extracted, using text mode for analysis")
                        analysis = self._call_text_llm(dxf_text)
                        result["visual_analysis"] = analysis
                        result["success"] = True
                        logger.info("VisualReader: text analysis complete")
                        return result

                except Exception as e:
                    logger.warning(f"VisualReader: DXF text extraction failed ({e})")
                    if mode == "text":
                        result["error"] = f"DXF 文本提取失败: {e}"
                        return result
                    # auto 模式回退到视觉模式
                    logger.info("VisualReader: falling back to vision mode...")

            # ── 视觉模式：SVG/PNG + 多模态 LLM ──
            logger.info("VisualReader: capturing AutoCAD snapshot...")
            try:
                # 尝试矢量导出（DXF→SVG）
                snapshot_b64 = self.snapshot.capture_vector_base64(
                    white_to_black=True,
                )
                result["snapshot_base64"] = snapshot_b64
                result["snapshot_format"] = "svg"
                logger.info("VisualReader: vector SVG captured")
            except Exception as e:
                logger.warning(f"VisualReader: vector export failed ({e}), falling back to raster")
                try:
                    snapshot_b64 = self.snapshot.capture(upscale=True)
                    result["snapshot_base64"] = snapshot_b64
                    result["snapshot_format"] = "png"
                    logger.info("VisualReader: raster PNG captured (fallback)")
                except Exception as e2:
                    logger.error(f"VisualReader: raster fallback also failed: {e2}")
                    err_msg = str(e2)
                    if "HWND" in err_msg or "not connected" in err_msg.lower():
                        result["error"] = (
                            "截图失败：AutoCAD 窗口句柄获取失败。"
                            "请确保 AutoCAD 已打开图纸并处于前台。"
                            f" 原始错误: {err_msg}"
                        )
                    else:
                        result["error"] = f"截图失败: {err_msg}"
                    return result

            # 调用多模态 LLM
            logger.info("VisualReader: calling multimodal LLM for analysis...")
            analysis = self._call_vision_llm(result["snapshot_base64"])
            result["visual_analysis"] = analysis
            result["success"] = True
            logger.info("VisualReader: analysis complete")

        except Exception as e:
            logger.error(f"VisualReader: analysis failed: {e}")
            result["error"] = f"视觉分析失败: {e}"

        return result

    # 文本模式分析 Prompt（无需多模态）
    TEXT_ANALYSIS_PROMPT = """你是一位资深电气工程师，正在审阅一份从 DXF 图纸中提取的结构化文本数据。

以下是 DXF 文件中的文字标注、图层信息和推断的连接关系。请基于这些数据回答：

## 1. 这是什么图纸？
- 图纸类型（主接线图、配电系统图等）
- 项目名称、电压等级
- 图纸编号

## 2. 主要电气设备
- 列出所有识别到的设备（变压器、断路器、GIS、开关柜、电缆等）
- 标注规格参数（容量、电压、电流等）
- 数量统计

## 3. 系统拓扑
- 描述从电源到负荷的电气路径
- 母线配置（单母线/双母线/分段）
- 关键连接关系

## 4. 发现的问题或异常
- 标注不一致的地方
- 明显缺失的信息
- 其他值得注意的点

请以 JSON 格式输出：
{
  "drawing_type": "主接线图",
  "project_name": "...",
  "voltage_levels": ["220kV", "66kV"],
  "devices": [
    {"type": "变压器", "label": "1#主变", "spec": "SZ-295000/230", "count": 2}
  ],
  "topology": "从220kV系统经GIS接入主变，降压至66kV后...",
  "issues": ["..."]
}"""

    def _call_text_llm(self, dxf_text: str) -> dict:
        """
        调用纯文本 LLM 分析 DXF 提取的结构化文本

        Args:
            dxf_text: DXF 提取的结构化 Markdown 文本

        Returns:
            LLM 返回的 JSON 分析结果
        """
        from agent.llm_factory import create_primary_llm
        from langchain_core.messages import HumanMessage, SystemMessage

        # 截断过长文本（保留前 12000 字符）
        if len(dxf_text) > 12000:
            dxf_text = dxf_text[:12000] + "\n\n... (文本已截断)"

        try:
            llm = create_primary_llm(
                temperature=0.1,
                max_tokens=4096,
            )
            messages = [
                SystemMessage(content="你是一位资深电气工程师，擅长分析电气图纸的结构化文本数据。请严格以 JSON 格式输出分析结果。"),
                HumanMessage(content=f"{self.TEXT_ANALYSIS_PROMPT}\n\n---\n以下是 DXF 提取的结构化数据：\n\n{dxf_text}"),
            ]
            resp = llm.invoke(messages)
            content = resp.content if hasattr(resp, 'content') else str(resp)
            return self._parse_llm_json(content)

        except Exception as e:
            logger.error(f"Text LLM call failed: {e}")
            return {"error": f"LLM 调用失败: {e}", "raw": ""}

    def _call_vision_llm(self, image_b64: str) -> dict:
        """
        调用多模态 LLM 分析图纸截图

        Args:
            image_b64: base64 编码的截图（含 data:image/png;base64, 前缀）

        Returns:
            LLM 返回的 JSON 分析结果
        """
        from agent.llm_factory import create_vision_llm
        from langchain_core.messages import HumanMessage

        try:
            llm = create_vision_llm(
                temperature=0.1,
                max_tokens=4096,
            )

            msg = HumanMessage(
                content=[
                    {"type": "image_url", "image_url": {"url": image_b64, "detail": "high"}},
                    {"type": "text", "text": self.ANALYSIS_PROMPT},
                ]
            )
            resp = llm.invoke([msg])
            content = resp.content if hasattr(resp, 'content') else str(resp)
            return self._parse_llm_json(content)

        except Exception as e:
            logger.error(f"Vision LLM call failed: {e}")
            return {"error": f"LLM 调用失败: {e}", "raw": ""}

    def _parse_llm_json(self, content: str) -> dict:
        """从 LLM 响应中提取 JSON"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # 尝试提取 ```json ... ``` 块
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试提取第一个 { ... } 块
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        logger.warning(f"VisualReader: could not parse LLM JSON, raw: {content[:300]}")
        return {"raw_response": content, "parse_error": True}

    def format_for_agent(self, visual_result: dict, com_result: str = "") -> str:
        """
        将视觉分析结果格式化为 Agent 可读的文本

        Args:
            visual_result: read() 返回的结果
            com_result: COM 查询结果文本（可选，用于对比）

        Returns:
            格式化的文本描述
        """
        if not visual_result.get("success"):
            return f"视觉分析失败: {visual_result.get('error', '未知错误')}"

        analysis = visual_result.get("visual_analysis", {})
        if not analysis or analysis.get("parse_error"):
            raw = analysis.get("raw_response", "无内容")
            return f"[视觉分析] LLM 原始输出:\n{raw[:2000]}"

        lines = ["## 视觉化图纸分析结果\n"]

        # 概览
        overview = analysis.get("overview", {})
        if overview:
            lines.append("### 图纸概览")
            lines.append(f"- 图纸类型: {overview.get('drawing_type', '未知')}")
            lines.append(f"- 电压等级: {overview.get('voltage_level', '未标注')}")
            lines.append(f"- 完整度: {overview.get('completeness', '未知')}")
            issues = overview.get("issues", [])
            if issues:
                lines.append(f"- 发现的问题: {', '.join(issues)}")
            lines.append("")

        # 设备
        devices = analysis.get("devices", [])
        if devices:
            lines.append(f"### 识别到的设备 ({len(devices)} 个)")
            for d in devices:
                label = d.get("label", "")
                label_str = f" ({label})" if label else ""
                count_val = d.get("count", 1)
                try:
                    count_val = int(count_val)
                except (ValueError, TypeError):
                    count_val = 1
                lines.append(
                    f"- {d.get('type', '未知设备')}{label_str} — {d.get('position', '未知位置')}"
                    + (f" x{count_val}" if count_val > 1 else "")
                )
            lines.append("")

        # 文字
        texts = analysis.get("texts", [])
        if texts:
            lines.append(f"### 文字标注 ({len(texts)} 处)")
            for t in texts:
                ctx = f" ({t.get('context', '')})" if t.get("context") else ""
                lines.append(f"- \"{t.get('content', '?')}\" — {t.get('position', '未知位置')}{ctx}")
            lines.append("")

        # 连接
        connections = analysis.get("connections", [])
        if connections:
            lines.append(f"### 连接关系 ({len(connections)} 条)")
            for c in connections:
                lines.append(f"- {c.get('from', '?')} → {c.get('to', '?')}")
                if c.get("description"):
                    lines.append(f"  {c['description']}")
            lines.append("")

        # 对比 COM 结果
        if com_result:
            lines.append("### 与 COM 查询对比")
            lines.append("以下为 COM API 直接读取的图元列表，可与视觉分析交叉验证：")
            lines.append(com_result)

        return "\n".join(lines)


# 全局单例
visual_reader = VisualReader()
