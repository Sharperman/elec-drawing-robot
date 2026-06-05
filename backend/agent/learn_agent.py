"""
LearnAgent - 参考图纸学习 Agent

多尺度图纸学习流程：
1. 打开并识别图纸（全局 + 多区域放大截图）
2. ezdxf 结构化提取 + 视觉 LLM 分析
3. 交互式对话（不懂的裁剪截图问用户，用户回复）
4. 提取 DrawingPattern 存入数据库
"""
import json
import os
import uuid
import base64
import re
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Generator, AsyncGenerator, Dict, List

from langchain_core.messages import (
    HumanMessage, SystemMessage, AIMessage,
)
from loguru import logger

from autocad.connection import autocad_connection
from autocad.zoom_control import ZoomController, get_zoom_controller
from autocad.canvas_state import CanvasState
from autocad.dxf_text_extractor import dxf_text_extractor
from autocad.snapshot import autocad_snapshot
from agent.llm_factory import create_primary_llm, create_vision_llm
from models.drawing_pattern import DrawingPattern
from models.session import get_db, get_engine, get_session_local


# ── 学习系统 Prompt ────────────────────────────────

SYSTEM_PROMPT = """你是一位资深电气工程师，正在通过 AutoCAD 视口"阅读"一张电气图纸。
你的工作方式就像一个工程师坐在电脑前看图：
- 先看全局（ZoomExtents）
- 再放大关注局部细节（ZoomWindow / ZoomCenter）
- 识别设备、标注、连接关系
- 遇到不清楚的地方，截取该区域图片问用户

你最终需要输出一个"图纸模式（DrawingPattern）"，包含：
1. 图纸整体框架（类型、电压等级、系统拓扑）
2. 每个典型设备的名称、类型、典型位置规律
3. 标注风格（字体大小、位置习惯、编号规则）
4. 连接模式（母线→断路器→变压器的连接规律）
5. 图层使用规范

在整个学习过程中，如果有任何看不清楚、拿不准的地方，
你必须主动截图（描述坐标区域）并提问，不要让用户猜。
用户会用自然语言回答你的提问。
"""

ZOOM_INSTRUCTION = """## 缩放控制（由系统自动执行，你只需描述意图）

系统会按以下顺序为你自动缩放并执行截图，你不需要调用任何工具：
1. 全局视图截图（ZoomExtents）
2. 左上区域放大截图
3. 右上区域放大截图
4. 左下区域放大截图
5. 右下区域放大截图
6. 回到全局视图

如果你需要更精细的局部放大（比如"请放大断路器 QF1 周围"），
请在回复中说明，系统会执行 ZoomWindow 后截图给你。
"""

ANALYSIS_PROMPT = """你是一位资深电气工程制图专家。你需要将以下多尺度截图分析结果整理成一份**完整的 DrawingPattern 模板**，供 AI 绘图 Agent 未来复现同类图纸时使用。

# 🔴 核心原则：宁可冗余，不可遗漏

1. **必须穷尽**：从截图中提取**每一个**设备、**每一处**标注、**每一条**连接关系。不要做"代表性枚举"。
2. **不要简化**：即使图纸内容很少（如只有集电线路），也要完整描述所有可见元素。
3. **推断制图习惯**：从标注位置、文字大小、箭头样式、线型粗细等推断制图规范。
4. **禁止空字段**：如果某个字段确实无法确定，写明原因（如"图中未见该类型"），不要留 null / [] / ""。

# 📋 信息来源
- **截图分析汇总**（多尺度视觉 LLM 逐区域分析结果）
- **文本提取**（ezdxf 或 AutoCAD COM 提取的标注文字）
- **用户补充信息**（用户额外说明）

---

## 截图分析汇总
{screenshots_analysis}

## 文本提取
{dxf_text}

## 用户补充信息
{user_feedback}

---

# 📤 输出格式

必须输出如下完整 JSON。**每个字段都必须有实际内容**，除非确实不存在。

```json
{{
  "name": "图纸名称（如：35kV集电线路接线图 / 220kV升压站主接线图）。如果截图中没有明确标题，请根据图纸内容推断一个准确的名称",
  "description": "【不少于100字】详细描述：(1)图纸的设计用途和电压等级 (2)电气拓扑结构 (3)主要设备类型和数量 (4)图纸的整体布局方向 (5)特殊设计特点 (6)标注风格和制图习惯",
  "drawing_habits": {{
    "title_block_position": "标题栏位置（右下角/右下角带图框/无标题栏）",
    "scale": "推断的图纸比例（如 1:100），无法判断则写 unknown",
    "unit": "图纸单位（mm/cm/m），通常电气图纸为 mm",
    "line_weights": {{"thin": "细线对象类型（如标注线）", "thick": "粗线对象类型（如主母线、电缆）"}},
    "fonts": ["观察到的所有字体（如 Simplex, HZTXT）"],
    "typical_text_height": 3.5,
    "grid_reference": "是否有网格/参考坐标系？格式是什么样的？",
    "page_size": "如 A1/A2/A3，无法判断写 unknown",
    "other_conventions": ["其他观察到的制图习惯，如设备编号规则、图例位置等"]
  }},
  "topology": {{
    "type": "拓扑类型（如：单母线分段 / 双母线带旁路 / 链式集电线路 / 放射式馈线 / 桥型接线）",
    "voltage_levels": ["所有出现的电压等级，如 35kV, 10kV, 0.4kV"],
    "arrangement": "设备排列方向描述（如：进线在左侧→母线水平→馈线向下引出）",
    "bus_configuration": "母线配置（单母线/双母线/无母线-链式），如为链式接线，请特别说明",
    "incoming_lines": 进线回路数量,
    "outgoing_lines": 出线回路数量,
    "key_features": ["列举3-8个关键设计特征"],
    "redundancy": "是否有冗余设计（备用回路/旁路/联络开关等）"
  }},
  "devices": [
    {{
      "type": "设备类型（如：真空断路器、隔离开关、电流互感器、避雷器、电缆终端头、箱变、风机）",
      "symbol_id": "对应的 AutoCAD 图块名或符号 ID（如 CB_3P, CT_CORE, LA_HV），无法确定写 unknown",
      "label_pattern": "标注命名规则（如：QF{{}}, T{{}}, QS{{}}，用{{}}表示编号占位符），如果没有标注则写 无标注",
      "count": 该类型设备在图中的总数，未全部可见则估算并标注 约X个,
      "typical_position": {{"description": "设备在图纸中的典型位置描述", "coordinates": "如有坐标则填"}},
      "connections": ["该设备典型接什么（上游→下游），如：一端接母线，一端接电缆"],
      "manufacturer_info": "如果标注了厂家/型号信息，一并记录",
      "notes": "设备特殊说明（如有铭牌参数、安装要求标记等）"
    }}
  ],
  "cables_and_lines": [
    {{
      "cable_id": "电缆编号（如 CABLE-01, ZC-YJV22-3×240），截图中有则填",
      "type": "电缆/导线类型（如：铜芯电缆、钢芯铝绞线、封闭母线）",
      "specification": "规格型号（如 3×240mm², LGJ-240/30）",
      "from_device": "起点设备",
      "to_device": "终点设备",
      "length": "电缆长度（如有标注）",
      "routing": "敷设方式（如直埋、电缆沟、桥架、架空）"
    }}
  ],
  "layout_rules": [
    "描述5-10条具体的布局规律。例如：",
    "主母线水平布置在图纸上方占图纸宽度80%",
    "所有断路器垂直排列，间距约 60-80mm",
    "标注文字位于设备右上方，字高约 3.5mm",
    "进线回路从左进入，出线回路向右引出",
    "同电压等级设备集中在同一区域",
    "导线拐弯均为直角或45度角",
    "母线与分支线用不同线型/颜色区分"
  ],
  "annotation_style": {{
    "font_height": 标注文字字高（mm）,
    "font_family": "推断的字体（如 Simplex, HZTXT, ISOCP）",
    "prefixes": {{"所有观察到的前缀规则，如：breaker→QF, transformer→T, disconnector→QS, CT→CT, PT→PT, cable→CABLE, bus→BUS"}},
    "numbering_pattern": "编号规则（如：QF01, QF02... 顺序编号 / 按位置编号 / 无编号）",
    "position": "标注位置：top_right/bottom_center/left/top_left",
    "alignment": "标注对齐方式：左对齐/居中/右对齐",
    "text_layer": "标注所在的图层名（如有）",
    "leader_style": "指引线样式（有箭头/无箭头/圆点/斜线）"
  }},
  "connection_patterns": [
    {{
      "from_type": "起点设备类型",
      "to_type": "终点设备类型",
      "via": "连接方式（导线/电缆/母线/跳线）",
      "wire_type": "线型（实线/虚线/点划线）",
      "wire_color_or_layer": "线所在的图层名或颜色（如有）",
      "typical_length": 典型连接长度（mm）或 根据布局确定,
      "junction_style": "连接点样式（圆点/方块/无标记/T接/十字交叉）",
      "notes": "该连接的补充说明"
    }}
  ],
  "layer_spec": {{
    "bus": "母线图层（如 ELEC-BUS）",
    "wire": "导线图层（如 ELEC-WIRE）",
    "device": "设备图层（如 ELEC-DEVICE）",
    "text": "文字图层（如 ELEC-TEXT）",
    "dimension": "尺寸标注图层",
    "border": "图框图框图层",
    "others": ["其他观察到的图层"]
  }},
  "bill_of_materials": {{
    "has_bom_table": true或false，图中是否有材料清单表,
    "position": "材料表的位置（如：图纸右下角/无材料表）",
    "columns_observed": ["观察到的表头列名，如 序号, 名称, 型号规格, 单位, 数量, 备注"]
  }}
}}
```

# 🔴 输出规则（必须严格遵守）

1. **只输出 JSON**，不要任何解释性文字、不要```json```包裹、不要Markdown。
2. **每个字段都要填充**，如果一个字段原样复制了示例值（如 "ELEC-BUS"），说明你没有认真分析——必须根据截图中真实情况填写。
3. **devices 数组不能为空**，如果图中确实没有设备，请说明图中只有哪些元素（如导线、标注、图框）。
4. **layout_rules 至少 5 条**，从截图分析中归纳。
5. **description 至少 100 字**，全面描述图纸用途、结构、特点。
6. 如果某些信息无法从截图中确定，标注为 "unknown" 或 "截图中未显示"，而不是留空。
7. 电缆和导线信息极其重要，必须填入 cables_and_lines。

记住：你的输出将直接决定 AI 绘图 Agent 能否**正确复现这张图纸**。详细信息越多，复现越准确。"""


class LearnAgent:
    """
    参考图纸学习 Agent

    使用方式：
    - 创建实例后调用 learn(file_path) 启动学习流程
    - 通过 SSE 事件流与前端对话（提问 → 等待用户回复 → 继续）
    """

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.zoom_ctrl = get_zoom_controller()
        self.canvas_state = CanvasState(session_id, f"learn_{session_id}")
        self._screenshots: list[dict] = []       # 截图历史
        self._pattern: Optional[dict] = None       # 正在构建的 pattern
        self._user_feedback: list[str] = []       # 用户补充信息
        self._current_file: Optional[str] = None   # 当前学习文件

    # ── 公开方法 ────────────────────────────────────────

    def learn_stream(
        self,
        file_path: str,
    ) -> Generator[dict, None, None]:
        """
        学习流程（SSE 事件流）

        Yields 事件字典，每个字典会被序列化为 SSE。
        事件类型与前端 LearnSSEEvent 一一对应：
        {"type": "progress"|"screenshot"|"analysis"|"question"|"pattern"|"done"|"error", ...}

        完整流程：
        1. 打开图纸（AutoCAD 或 PDF 解析）
        2. 多尺度截图/页面提取 → 视觉分析
        3. 汇总分析，生成 DrawingPattern
        4. 展示 Pattern 供前端确认保存
        """
        self._current_file = file_path
        self._screenshots.clear()
        self._user_feedback.clear()

        ext = Path(file_path).suffix.lower()

        try:
            if ext == ".pdf":
                # ── PDF 分支：提取页面为图像 ──────────────────
                yield {
                    "type": "progress",
                    "phase": "upload",
                    "message": f"正在解析 PDF：{Path(file_path).name}",
                }
                pdf_pages = self._extract_pdf_pages(file_path)
                if not pdf_pages:
                    yield {
                        "type": "error",
                        "error": "无法解析 PDF，请检查文件是否损坏",
                    }
                    return
                yield {
                    "type": "progress",
                    "phase": "upload",
                    "message": f"✓ PDF 已解析，共 {len(pdf_pages)} 页",
                }

                # 逐页视觉分析
                yield {
                    "type": "progress",
                    "phase": "capture",
                    "message": "正在逐页分析 PDF 页面...",
                }
                for i, page_b64 in enumerate(pdf_pages, 1):
                    desc = f"PDF 第 {i} 页"
                    yield {
                        "type": "progress",
                        "phase": "analyze",
                        "message": f"正在分析：{desc} ...",
                    }
                    analysis = self._analyze_screenshot(page_b64, desc)

                    self._screenshots.append({
                        "step": i,
                        "description": desc,
                        "type": "pdf_page",
                        "screenshot": page_b64,
                        "analysis": analysis,
                    })

                    yield {
                        "type": "screenshot",
                        "screenshot_b64": page_b64,
                        "description": desc,
                        "analysis": json.dumps(analysis, ensure_ascii=False) if analysis else "",
                    }

                    # 检测 LLM 是否不支持图片输入
                    if isinstance(analysis, dict) and analysis.get("vision_unsupported"):
                        yield {
                            "type": "progress",
                            "phase": "analyze",
                            "message": "⚠ 当前 LLM 不支持图片分析。请前往「设置 → LLM 供应商」配置支持图片的模型（如 OpenAI GPT-4o / Gemini），否则 Pattern 生成将仅依赖页面文本。",
                        }

                # PDF 无 ezdxf 结构
                dxf_text = ""
                yield {"type": "progress", "phase": "extract", "message": "PDF 无 DXF 结构化数据"}

            else:
                # ── DWG/DXF 分支：AutoCAD 多尺度学习 ─────────
                # ── Step 1: 打开图纸 ──────────────────
                yield {
                    "type": "progress",
                    "phase": "upload",
                    "message": f"正在打开图纸：{Path(file_path).name}",
                }
                open_ok = self._open_drawing(file_path)
                if not open_ok:
                    yield {
                        "type": "error",
                        "error": "无法打开图纸，请确保 AutoCAD 已启动并且文件存在",
                    }
                    return
                yield {
                    "type": "progress",
                    "phase": "upload",
                    "message": "✓ 图纸已打开",
                }

                # ── Step 2: 多尺度截图 ──────────────────
                yield {
                    "type": "progress",
                    "phase": "zoom",
                    "message": "多尺度截图学习：将依次执行全局视图 → 4 个区域局部放大",
                }

                seq = self.zoom_ctrl.learn_zoom_sequence()
                for step_info in seq:
                    step_type = step_info["type"]
                    desc = step_info["description"]

                    yield {
                        "type": "progress",
                        "phase": "capture",
                        "message": f"步骤 {step_info['step']}：{desc}",
                    }

                    # 执行缩放
                    if step_type == "extents":
                        ok = self.zoom_ctrl.zoom_extents()
                    elif step_type == "window":
                        p = step_info["params"]
                        ok = self.zoom_ctrl.zoom_window(p["x1"], p["y1"], p["x2"], p["y2"])
                    else:
                        ok = False

                    if not ok:
                        yield {"type": "progress", "phase": "capture", "message": f"⚠ 缩放失败：{desc}"}
                        continue

                    # 截图
                    screenshot_b64 = self._capture_screenshot()
                    if not screenshot_b64:
                        yield {"type": "progress", "phase": "capture", "message": f"⚠ 截图失败：{desc}"}
                        continue

                    # 视觉分析
                    yield {"type": "progress", "phase": "analyze", "message": f"正在分析：{desc} ..."}
                    analysis = self._analyze_screenshot(screenshot_b64, desc)

                    self._screenshots.append({
                        "step": step_info["step"],
                        "description": desc,
                        "type": step_type,
                        "screenshot": screenshot_b64,
                        "analysis": analysis,
                    })

                    # 发送截图 + 分析结果给前端（screenshot_b64 为原始 base64，前端会加前缀）
                    yield {
                        "type": "screenshot",
                        "screenshot_b64": screenshot_b64,
                        "description": f"步骤 {step_info['step']}：{desc}",
                        "analysis": json.dumps(analysis, ensure_ascii=False) if analysis else "",
                    }

                    # 检测 LLM 是否不支持图片输入
                    if isinstance(analysis, dict) and analysis.get("vision_unsupported"):
                        yield {
                            "type": "progress",
                            "phase": "analyze",
                            "message": "⚠ 当前 LLM 不支持图片分析。请前往「设置 → LLM 供应商」配置支持图片的模型（如 OpenAI GPT-4o / Gemini），否则 Pattern 生成将仅依赖 ezdxf 结构化数据。",
                        }

                # ── Step 3: ezdxf 结构化提取 ─────────
                yield {"type": "progress", "phase": "extract", "message": "正在使用 ezdxf 提取图纸结构化文本..."}
                dxf_text = self._extract_dxf_text(file_path)

                if dxf_text:
                    yield {
                        "type": "progress",
                        "phase": "extract",
                        "message": f"✓ ezdxf 提取完成 — {len(dxf_text)} 字符的结构化数据",
                    }
                else:
                    dxf_text = ""
                    yield {"type": "progress", "phase": "extract", "message": "⚠ ezdxf 未能提取文本，将仅依赖视觉分析"}

            # ── Step 4: 汇总分析，生成 Pattern ───
            yield {"type": "progress", "phase": "pattern", "message": "正在汇总多尺度分析结果，生成 DrawingPattern..."}

            pattern = self._generate_pattern(dxf_text)

            if not pattern:
                yield {"type": "error", "error": "无法生成图纸模式，请检查 LLM 配置"}
                return

            self._pattern = pattern

            # ── Step 5: 展示 Pattern ─
            pattern_summary = self._format_pattern_summary(pattern)
            yield {
                "type": "pattern",
                "pattern": pattern,
                "message": pattern_summary,
            }

            # 提示用户可确认保存
            yield {
                "type": "done",
                "message": "学习完成！请在右侧面板查看图纸模式，点击「确认保存」将模式存入知识库。",
                "pattern": pattern,
            }

        except Exception as e:
            logger.error(f"LearnAgent 错误: {e}")
            import traceback
            traceback.print_exc()
            yield {"type": "error", "error": f"学习过程出错：{str(e)[:200]}"}

    def confirm_and_save(
        self,
        pattern_overrides: Optional[dict] = None,
        user_notes: Optional[str] = None,
    ) -> dict:
        """
        确认并保存 Pattern 到数据库

        Args:
            pattern_overrides: 用户编辑后的 pattern 字段（部分覆盖）
            user_notes:       用户补充的说明

        Returns:
            保存结果 {"success": bool, "pattern_id": int, "message": str}
        """
        try:
            import json

            pattern = dict(self._pattern) if self._pattern else {}

            # 应用用户的覆盖
            if pattern_overrides:
                for k, v in pattern_overrides.items():
                    pattern[k] = v

            if user_notes:
                self._user_feedback.append(user_notes)
                notes_key = "user_notes"
                pattern[notes_key] = user_notes

            # 写入数据库
            engine = get_engine()
            from sqlalchemy.orm import sessionmaker
            SessionLocal = sessionmaker(bind=engine)
            db = SessionLocal()
            try:
                dp = DrawingPattern(
                    name=pattern.get("name", Path(self._current_file or "unknown").stem),
                    description=pattern.get("description", ""),
                    source_file=self._current_file,
                    source_type=Path(self._current_file).suffix.lstrip(".") if self._current_file else "dwg",
                )
                # 写 JSON 字段
                for key in (
                    "topology", "devices", "layout_rules",
                    "annotation_style", "connection_patterns", "layer_spec",
                    "visual_analysis",
                ):
                    if key in pattern:
                        val = pattern[key]
                        setattr(dp, key, json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val))

                if self._screenshots:
                    # 保存第一张截图为缩略图
                    try:
                        thumb_dir = Path("data/pattern_thumbnails")
                        thumb_dir.mkdir(parents=True, exist_ok=True)
                        thumb_path = thumb_dir / f"{uuid.uuid4().hex[:8]}.png"
                        import base64
                        with open(thumb_path, "wb") as f:
                            f.write(base64.b64decode(self._screenshots[0]["screenshot"]))
                        dp.thumbnail_path = str(thumb_path)
                    except Exception:
                        pass

                db.add(dp)
                db.commit()
                db.refresh(dp)

                pid = dp.id
                logger.info(f"DrawingPattern 已保存: id={pid}, name={dp.name}")
                return {"success": True, "pattern_id": pid, "message": f"图纸模式已保存（ID: {pid}）"}

            finally:
                db.close()

        except Exception as e:
            logger.error(f"保存 Pattern 失败: {e}")
            return {"success": False, "message": f"保存失败：{str(e)[:200]}"}

    # ── 内部方法 ────────────────────────────────────────

    def _extract_pdf_pages(self, file_path: str, dpi: int = 200, max_pages: int = 5) -> List[str]:
        """
        用 PyMuPDF 提取 PDF 页面为 base64 PNG 图像列表

        Args:
            file_path: PDF 文件路径
            dpi: 渲染分辨率（默认 200，足够看清图纸细节）
            max_pages: 最多处理页数（默认 5，防止大文档卡死）

        Returns:
            每页图像的 base64 字符串列表
        """
        try:
            import fitz  # PyMuPDF
            import io
            from PIL import Image

            pages_b64: List[str] = []
            doc = fitz.open(file_path)
            total = len(doc)
            page_count = min(total, max_pages)

            zoom = dpi / 72.0  # PDF 默认 72 DPI
            mat = fitz.Matrix(zoom, zoom)

            for i in range(page_count):
                page = doc.load_page(i)
                pix = page.get_pixmap(matrix=mat)
                img_data = pix.tobytes("png")
                b64 = base64.b64encode(img_data).decode("utf-8")
                pages_b64.append(b64)

            doc.close()
            logger.info(f"PDF 提取完成: {file_path}, 共 {page_count}/{total} 页")
            return pages_b64

        except Exception as e:
            logger.error(f"PDF 提取失败: {e}")
            return []

    def _open_drawing(self, file_path: str) -> bool:
        """通过 AutoCAD COM 打开用户上传的图纸文件"""
        import pythoncom
        try:
            pythoncom.CoInitialize()
            # 确保已连接
            ok = autocad_connection.connect()
            if not ok or not autocad_connection.is_connected:
                logger.warning("AutoCAD 未连接")
                return False

            acad = autocad_connection.acad
            if acad is None:
                logger.warning("AutoCAD Application 对象为空")
                return False

            abs_path = str(Path(file_path).resolve())
            logger.info(f"正在 AutoCAD 中打开: {abs_path}")

            # 通过 Documents 集合打开文件
            try:
                new_doc = acad.Documents.Open(abs_path)
                logger.info(f"已在 AutoCAD 中打开: {new_doc.Name}")
            except Exception as e:
                # 如果文件已经在当前标签页打开，忽略
                err = str(e)[:200]
                if "already open" in err.lower() or "eAlreadyOpen" in err:
                    logger.info(f"文件已在 AutoCAD 中打开: {abs_path}")
                else:
                    logger.error(f"打开 DWG 失败: {err}")
                    return False

            return True
        except Exception as e:
            logger.error(f"打开图纸失败: {e}")
            return False

    def _capture_screenshot(self) -> Optional[str]:
        """截图并返回 base64 字符串"""
        try:
            b64 = autocad_snapshot.capture(upscale=True)
            return b64
        except Exception as e:
            logger.warning(f"截图失败: {e}")
            return None

    def _analyze_screenshot(self, screenshot_b64: str, description: str) -> dict:
        """调用视觉 LLM 分析单张截图。优先使用数据库中配置的多模态 LLM。"""
        db = None
        try:
            # capture() 返回的 base64 可能带 data URI 前缀，需要剥离
            if screenshot_b64.startswith("data:"):
                screenshot_b64 = screenshot_b64.split(",", 1)[-1]

            db = get_session_local()()
            llm = create_vision_llm(db=db)
            msg = HumanMessage(content=[
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{screenshot_b64}", "detail": "high"}},
                {"type": "text", "text": f"这是电气图纸的「{description}」视图。\n\n请识别：1. 可见的电气设备（类型、标注）2. 文字标注内容 3. 连接关系 4. 该区域的布局特点\n\n用 JSON 格式输出。"},
            ])
            resp = llm.invoke([msg])
            content = resp.content if hasattr(resp, "content") else str(resp)
            return self._parse_json(content)
        except Exception as e:
            err_str = str(e)
            logger.error(f"视觉分析失败 ({description}): {err_str}")
            # 判断是否为 LLM 不支持图片输入
            if "support image input" in err_str or "No endpoints found" in err_str:
                return {"vision_unsupported": True, "error": "当前配置的 LLM 不支持图片输入"}
            return {"error": err_str}
        finally:
            if db:
                db.close()

    def _extract_dxf_text(self, file_path: str) -> str:
        """提取图纸文本。DXF 用 ezdxf，DWG 用 AutoCAD COM"""
        ext = Path(file_path).suffix.lower()
        if ext == '.dwg':
            return self._extract_dwg_text_acad(file_path)
        # DXF: 用 ezdxf
        try:
            return dxf_text_extractor.extract_from_dxf(file_path)
        except Exception as e:
            logger.warning(f"ezdxf 提取失败: {e}")
            return ""

    def _extract_dwg_text_acad(self, file_path: str) -> str:
        """通过 AutoCAD COM 提取 DWG 文件中的文本"""
        try:
            from autocad.connection import autocad_connection
            if not autocad_connection.app:
                logger.warning("AutoCAD 未连接，无法提取 DWG 文本")
                return ""
            doc = autocad_connection.doc
            text_parts = []
            for entity in doc.ModelSpace:
                try:
                    if hasattr(entity, 'TextString'):
                        text_parts.append(entity.TextString)
                    elif hasattr(entity, 'TagString'):
                        text_parts.append(f"[{entity.TagString}] {entity.TextString}")
                except Exception:
                    continue
                if len(text_parts) > 500:
                    break  # 防止超大文件
            result = "\n".join(text_parts[:500])
            logger.info(f"AutoCAD COM 提取到 {len(text_parts)} 个文本对象")
            return result
        except Exception as e:
            logger.warning(f"AutoCAD COM 文本提取失败: {e}")
            return ""

    def _generate_pattern(self, dxf_text: str) -> Optional[dict]:
        """汇总所有截图分析和 ezdxf 文本，生成 DrawingPattern"""
        try:
            import json

            # 拼接所有截图分析
            screenshots_analysis_parts = []
            vision_unsupported_count = 0
            for i, shot in enumerate(self._screenshots):
                analysis = shot.get("analysis", {})
                # 跳过 vision_unsupported 的标记，避免把错误信息传给 LLM
                if isinstance(analysis, dict) and analysis.get("vision_unsupported"):
                    vision_unsupported_count += 1
                    screenshots_analysis_parts.append(
                        f"### 截图 {shot['step']}（{shot['description']}）\n"
                        f"[视觉分析不可用：当前 LLM 不支持图片输入]"
                    )
                else:
                    analysis_str = json.dumps(analysis, ensure_ascii=False) if isinstance(analysis, (dict, list)) else str(analysis)
                    screenshots_analysis_parts.append(f"### 截图 {shot['step']}（{shot['description']}）\n{analysis_str[:3000]}")

            # 如果所有截图都没有视觉分析，给 LLM 额外提示
            if vision_unsupported_count == len(self._screenshots) and self._screenshots:
                screenshots_analysis_parts.insert(
                    0,
                    "【注意】当前 LLM 供应商不支持图片输入，以下仅为截图列表（无详细视觉分析）。"
                    "请基于截图描述、文件名称和上下文尽可能推断图纸模式。",
                )

            screenshots_analysis = "\n\n".join(screenshots_analysis_parts)

            user_feedback_str = "\n".join(self._user_feedback) if self._user_feedback else "（无）"

            prompt = ANALYSIS_PROMPT.format(
                screenshots_analysis=screenshots_analysis[:16000],
                dxf_text=(dxf_text or "")[:12000],
                user_feedback=user_feedback_str,
            )

            db2 = get_session_local()()
            llm = create_primary_llm(db=db2)
            resp = llm.invoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ])
            content = resp.content if hasattr(resp, "content") else str(resp)
            logger.debug(f"Pattern LLM raw output ({len(content)} chars): {content[:300]}")
            parsed = self._parse_json(content)
            logger.info(f"Pattern parsed: keys={list(parsed.keys())}, has_devices={bool(parsed.get('devices'))}, has_topology={bool(parsed.get('topology'))}")
            return parsed

        except Exception as e:
            logger.error(f"生成 Pattern 失败: {e}")
            return None
        finally:
            if 'db2' in dir() and db2:
                db2.close()

    def _parse_json(self, text: str) -> dict:
        """从 LLM 输出中提取 JSON，多级降级策略"""
        if not text:
            return {}

        # Level 1: 纯 JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Level 2: ```json ... ``` 代码块
        m = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?\s*```', text)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Level 3: 最外层 { ... } (从第一个 { 到最后一个 })
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group())
            except json.JSONDecodeError:
                # Level 3b: 清理常见问题（尾部逗号、注释等）
                cleaned = re.sub(r',\s*([}\]])', r'\1', m.group())  # 移除末尾逗号
                cleaned = re.sub(r'//[^\n]*', '', cleaned)          # 移除 C++ 风格注释
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

        # Level 4: 强按头 — 尝试用 ast.literal_eval
        try:
            import ast
            return ast.literal_eval(m.group() if m else text.lstrip())
        except Exception:
            pass

        # 兜底：记录原始输出方便排查
        logger.warning(f"LLM output not valid JSON, returning raw. First 200 chars: {text[:200]}")
        return {"raw": text[:500]}

    def _format_pattern_summary(self, pattern: dict) -> str:
        """格式化 Pattern 摘要（用于前端展示）"""
        lines = []
        lines.append(f"## {pattern.get('name', '未命名模式')}")
        if pattern.get("description"):
            lines.append(f"\n{pattern['description']}")

        # ── 拓扑 ──
        topo = pattern.get("topology", {})
        if topo:
            lines.append(f"\n**拓扑**：{topo.get('type', '未知')} | 电压：{', '.join(topo.get('voltage_levels', []))}")
            if topo.get("arrangement"):
                lines.append(f"  排布：{topo['arrangement']}")
            if topo.get("incoming_lines") or topo.get("outgoing_lines"):
                lines.append(f"  回路：进线 {topo.get('incoming_lines', '?')} / 出线 {topo.get('outgoing_lines', '?')}")
            if topo.get("key_features"):
                lines.append(f"  特征：{'; '.join(topo['key_features'][:5])}")

        # ── 设备 ──
        devices = pattern.get("devices", [])
        if devices:
            lines.append(f"\n**设备清单**（{len(devices)} 类）：")
            for d in devices[:10]:
                label = d.get('label_pattern', '?')
                cnt = d.get('count', '?')
                lines.append(f"  - {d.get('type', '?')} ×{cnt} 标注：{label}")

        # ── 电缆 ──
        cables = pattern.get("cables_and_lines", [])
        if cables:
            lines.append(f"\n**电缆/导线**（{len(cables)} 条）：")
            for c in cables[:5]:
                lines.append(f"  - {c.get('cable_id', '?')} {c.get('type', '?')} {c.get('specification', '')} "
                             f"({c.get('from_device', '?')} → {c.get('to_device', '?')})")

        # ── 布局规律 ──
        rules = pattern.get("layout_rules", [])
        if rules:
            lines.append(f"\n**布局规律**：")
            for r in rules[:8]:
                lines.append(f"  - {r}")

        # ── 标注风格 ──
        anno = pattern.get("annotation_style", {})
        if anno:
            lines.append(f"\n**标注**：字高 {anno.get('font_height', '?')}mm · {anno.get('font_family', '?')} · {anno.get('position', '?')}")

        # ── 制图习惯 ──
        habits = pattern.get("drawing_habits", {})
        if habits:
            lines.append(f"\n**制图习惯**：{habits.get('page_size', '?')} · 比例 {habits.get('scale', '?')} · 单位 {habits.get('unit', '?')}")
            if habits.get("other_conventions"):
                for c in habits["other_conventions"][:3]:
                    lines.append(f"  - {c}")

        return "\n".join(lines)

    def _event(self, event_type: str, **kwargs) -> dict:
        """构造 SSE 事件字典"""
        evt = {"type": event_type, "timestamp": datetime.utcnow().isoformat()}
        evt.update(kwargs)
        return evt

    def add_user_feedback(self, feedback: str) -> None:
        """添加用户反馈（在问答环节）"""
        self._user_feedback.append(feedback)


# ── 全局 LearnAgent 管理 ──────────────────────────────────

_learn_agents: dict[str, LearnAgent] = {}


def get_learn_agent(session_id: str) -> LearnAgent:
    """获取或创建 LearnAgent 实例"""
    if session_id not in _learn_agents:
        _learn_agents[session_id] = LearnAgent(session_id)
    return _learn_agents[session_id]


def clear_learn_agent(session_id: str) -> None:
    """清除 LearnAgent 实例（学习完成后）"""
    _learn_agents.pop(session_id, None)
