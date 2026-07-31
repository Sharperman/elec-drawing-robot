"""
DXF 结构化文本提取器

绕过 SVG/PNG 渲染，直接从 DXF 中提取结构化文本描述，
让 LLM 可以直接"读懂"图纸内容，无需多模态视觉能力。

输出格式：
- Markdown 结构化文本，包含文字标注、设备布局、连接拓扑
- 文字按空间位置分组，保留 CAD 坐标信息
- 线条/多段线提取为简化的连接描述
"""

from dataclasses import dataclass
import os
import tempfile

from loguru import logger


@dataclass
class TextEntity:
    """文字实体"""
    text: str
    x: float
    y: float
    height: float = 2.5
    rotation: float = 0.0
    layer: str = ""


@dataclass
class LineEntity:
    """线条实体（简化）"""
    x1: float
    y1: float
    x2: float
    y2: float
    layer: str = ""


class DXFTextExtractor:
    """
    DXF → 结构化文本提取器

    用法：
        extractor = DXFTextExtractor()
        text = extractor.extract()  # 从当前 AutoCAD 图纸提取
        # 或
        text = extractor.extract_from_dxf("path/to/file.dxf")
    """

    # 图纸区域划分（相对于 data range 的百分比）
    REGIONS = {
        "标题栏（右下角）":   (0.70, 0.00, 1.00, 0.15),
        "图纸说明（右上角）":  (0.70, 0.85, 1.00, 1.00),
        "图例区（左下角）":    (0.00, 0.00, 0.30, 0.15),
        "上部区域":            (0.00, 0.75, 1.00, 1.00),
        "中部区域":            (0.00, 0.35, 1.00, 0.75),
        "下部区域":            (0.00, 0.00, 1.00, 0.35),
    }

    def extract(self, output_dir: str | None = None) -> str:
        """
        从当前 AutoCAD 图纸提取结构化文本

        流程：
        1. AutoCAD COM SaveAs → 临时 DXF
        2. ezdxf 解析 → 提取文字/线条/图层信息
        3. 空间分组 → 结构化 Markdown

        Returns:
            结构化 Markdown 文本，可直接喂给 LLM
        """
        dxf_path = self._saveas_dxf(output_dir)
        try:
            return self.extract_from_dxf(dxf_path)
        finally:
            try:
                os.unlink(dxf_path)
            except Exception:
                pass

    def extract_from_dxf(self, dxf_path: str) -> str:
        """
        从 DXF 文件提取结构化文本

        Args:
            dxf_path: DXF 文件路径

        Returns:
            结构化 Markdown 文本
        """
        import ezdxf

        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        # 1. 提取文字
        texts = self._extract_texts(msp)

        # 2. 提取线条（简化拓扑）
        lines = self._extract_lines(msp)

        # 3. 提取图层信息
        layers = self._extract_layers(doc)

        # 4. 计算空间范围
        if texts:
            x_vals = [t.x for t in texts]
            y_vals = [t.y for t in texts]
            x_min, x_max = min(x_vals), max(x_vals)
            y_min, y_max = min(y_vals), max(y_vals)
        else:
            x_min = y_min = 0
            x_max = y_max = 100

        # 5. 构建输出
        return self._build_output(texts, lines, layers, x_min, y_min, x_max, y_max)

    # ──────────────────────────────────────────────
    # 提取方法
    # ──────────────────────────────────────────────

    def _extract_texts(self, msp) -> list[TextEntity]:
        """提取所有文字实体"""
        text_types = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}
        texts = []

        for e in msp:
            if e.dxftype() not in text_types:
                continue

            content = ""
            if e.dxftype() == "MTEXT":
                try:
                    content = e.plain_text() if hasattr(e, "plain_text") else ""
                except Exception:
                    content = ""
            else:
                try:
                    content = e.dxf.text if hasattr(e.dxf, "text") else ""
                except Exception:
                    content = ""

            content = str(content).strip()
            if not content:
                continue

            x = e.dxf.insert.x if hasattr(e.dxf, "insert") else 0
            y = e.dxf.insert.y if hasattr(e.dxf, "insert") else 0
            h = e.dxf.height if hasattr(e.dxf, "height") else 2.5
            rot = e.dxf.rotation if hasattr(e.dxf, "rotation") else 0.0
            layer = e.dxf.layer if hasattr(e.dxf, "layer") else ""

            texts.append(TextEntity(
                text=content,
                x=x, y=y,
                height=h,
                rotation=rot,
                layer=layer,
            ))

        logger.info(f"Extracted {len(texts)} text entities")
        return texts

    def _extract_lines(self, msp) -> list[LineEntity]:
        """提取线条实体（LINE 和 LWPOLYLINE）"""
        lines = []

        for e in msp:
            t = e.dxftype()
            layer = e.dxf.layer if hasattr(e.dxf, "layer") else ""

            if t == "LINE":
                try:
                    lines.append(LineEntity(
                        x1=e.dxf.start.x, y1=e.dxf.start.y,
                        x2=e.dxf.end.x, y2=e.dxf.end.y,
                        layer=layer,
                    ))
                except Exception:
                    pass
            elif t == "LWPOLYLINE":
                try:
                    pts = list(e.get_points("xy"))
                    for i in range(len(pts) - 1):
                        lines.append(LineEntity(
                            x1=pts[i][0], y1=pts[i][1],
                            x2=pts[i + 1][0], y2=pts[i + 1][1],
                            layer=layer,
                        ))
                except Exception:
                    pass

        logger.info(f"Extracted {len(lines)} line segments")
        return lines

    def _extract_layers(self, doc) -> dict[str, dict]:
        """提取图层信息"""
        layers = {}
        for layer in doc.layers:
            name = layer.dxf.name
            layers[name] = {
                "color": layer.dxf.color,
                "linetype": layer.dxf.linetype,
                "on": layer.is_on(),
                "frozen": layer.is_frozen(),
            }
        return layers

    # ──────────────────────────────────────────────
    # 输出构建
    # ──────────────────────────────────────────────

    def _build_output(
        self,
        texts: list[TextEntity],
        lines: list[LineEntity],
        layers: dict,
        x_min: float, y_min: float,
        x_max: float, y_max: float,
    ) -> str:
        """构建结构化 Markdown 输出"""
        parts = []

        # 头部：图纸基本信息
        parts.append("# 电气图纸 DXF 文本解析")
        parts.append("")
        parts.append(f"- 文字标注数量: {len(texts)}")
        parts.append(f"- 线条/多段线数量: {len(lines)}")
        parts.append(f"- 图层数量: {len(layers)}")
        parts.append(f"- 图纸坐标范围: X({x_min:.0f}~{x_max:.0f}), Y({y_min:.0f}~{y_max:.0f})")
        parts.append("")

        # 图层列表
        parts.append("## 图层列表")
        parts.append("")
        parts.append("| 图层名 | 颜色ACI | 线型 | 状态 |")
        parts.append("|--------|---------|------|------|")
        for name, info in sorted(layers.items()):
            status = []
            if not info["on"]:
                status.append("关闭")
            if info["frozen"]:
                status.append("冻结")
            status_str = "、".join(status) if status else "正常"
            parts.append(f"| {name} | {info['color']} | {info['linetype']} | {status_str} |")
        parts.append("")

        # 文字按空间区域分组
        grouped = self._group_texts_by_region(texts, x_min, y_min, x_max, y_max)

        parts.append("## 文字标注（按图纸区域分组）")
        parts.append("")

        for region_name, region_texts in grouped.items():
            if not region_texts:
                continue
            parts.append(f"### {region_name} ({len(region_texts)} 处)")
            parts.append("")

            # 去重并排序
            seen = set()
            unique = []
            for t in sorted(region_texts, key=lambda t: (-t.y, t.x)):
                key = (t.text, round(t.x, 0), round(t.y, 0))
                if key not in seen:
                    seen.add(key)
                    unique.append(t)

            for t in unique[:100]:  # 每区域最多100条
                parts.append(f"- `{t.text}` — 位置({t.x:.0f},{t.y:.0f}) 高{t.height:.1f}")
            if len(unique) > 100:
                parts.append(f"- ... (还有 {len(unique) - 100} 条)")
            parts.append("")

        # 设备/元件识别（基于文字模式匹配）
        parts.append("## 识别到的设备/元件（基于文字标注）")
        parts.append("")
        devices = self._identify_devices(texts)
        if devices:
            for category, items in sorted(devices.items()):
                parts.append(f"### {category}")
                for item in items:
                    parts.append(f"- {item}")
                parts.append("")
        else:
            parts.append("未识别到明确的设备标注。")
            parts.append("")

        # 连接关系推断（基于线条和文字位置）
        parts.append("## 连接拓扑（基于线条和文字位置推断）")
        parts.append("")
        topology = self._infer_topology(texts, lines, x_min, y_min, x_max, y_max)
        if topology:
            parts.append(topology)
        else:
            parts.append("线条数据量较大，建议结合文字标注理解连接关系。")
            parts.append("")

        # 独特的文字列表（去重后）
        unique_texts = sorted(set(t.text for t in texts))
        parts.append("## 所有独特文字标注（去重）")
        parts.append("")
        for i, txt in enumerate(unique_texts, 1):
            parts.append(f"{i}. {txt}")
        parts.append("")

        return "\n".join(parts)

    def _group_texts_by_region(
        self,
        texts: list[TextEntity],
        x_min: float, y_min: float,
        x_max: float, y_max: float,
    ) -> dict[str, list[TextEntity]]:
        """将文字按空间区域分组"""
        w = x_max - x_min
        h = y_max - y_min
        if w <= 0 or h <= 0:
            return {"全部区域": texts}

        grouped = {name: [] for name in self.REGIONS}

        for t in texts:
            rx = (t.x - x_min) / w
            ry = (t.y - y_min) / h

            placed = False
            for name, (rx0, ry0, rx1, ry1) in self.REGIONS.items():
                if rx0 <= rx <= rx1 and ry0 <= ry <= ry1:
                    grouped[name].append(t)
                    placed = True
                    break

            if not placed:
                grouped.setdefault("其他区域", []).append(t)

        return grouped

    def _identify_devices(self, texts: list[TextEntity]) -> dict[str, list[str]]:
        """基于文字内容识别设备"""
        import re

        categories = {
            "断路器": [r"QF\d*", r"断路器"],
            "隔离开关": [r"QS\d*", r"隔离开关", r"隔离开关"],
            "变压器": [r"变压器", r"主变", r"T\d+"],
            "母线": [r"母线", r"BUS", r"汇流排"],
            "电缆": [r"电缆", r"YJV", r"ZR-YJV"],
            "电压等级": [r"\d+\.?\d*kV", r"\d+V"],
            "接地": [r"接地", r"PE", r"地"],
            "避雷器": [r"避雷器", r"F\d*", r"SPD"],
            "互感器": [r"互感器", r"CT", r"PT", r"TV\d*", r"TA\d*"],
            "发电机": [r"发电机", r"G\d+"],
            "配电装置": [r"配电", r"开关柜", r"GIS"],
            "风机": [r"风机", r"风力", r"WT\d*"],
            "海底电缆": [r"海底电缆", r"海缆"],
            "升压设备": [r"升压"],
        }

        results = {}
        for t in texts:
            txt = t.text
            for cat, patterns in categories.items():
                for pat in patterns:
                    if re.search(pat, txt, re.IGNORECASE):
                        results.setdefault(cat, []).append(txt)
                        break

        return results

    def _infer_topology(
        self,
        texts: list[TextEntity],
        lines: list[LineEntity],
        x_min: float, y_min: float,
        x_max: float, y_max: float,
    ) -> str:
        """
        推断连接拓扑

        策略：找到线条端点附近的文字标注，推断设备间的连接关系
        """
        if not lines:
            return ""

        # 对大量线条做抽样（每10条取1条，最多500条）
        sample = lines[::max(1, len(lines) // 500)]

        # 构建文字的空间索引（网格划分）
        grid_size = max(x_max - x_min, y_max - y_min) / 20
        text_grid = {}
        for t in texts:
            gx = int((t.x - x_min) / grid_size)
            gy = int((t.y - y_min) / grid_size)
            text_grid.setdefault((gx, gy), []).append(t.text)

        # 找每条线两端的文字
        connections = []
        seen = set()

        for line in sample:
            # 找端点附近的文字
            t1 = self._find_nearest_text(line.x1, line.y1, text_grid,
                                         x_min, y_min, grid_size, texts)
            t2 = self._find_nearest_text(line.x2, line.y2, text_grid,
                                         x_min, y_min, grid_size, texts)

            if t1 and t2 and t1 != t2:
                key = tuple(sorted([t1, t2]))
                if key not in seen:
                    seen.add(key)
                    connections.append(f"{t1} ↔ {t2}")

        if not connections:
            return "未能从文字位置推断出明确的连接关系。"

        parts = ["以下为基于线条端点和文字位置推断的设备连接关系：", ""]
        for i, conn in enumerate(connections[:50], 1):
            parts.append(f"{i}. {conn}")

        if len(connections) > 50:
            parts.append(f"... (还有 {len(connections) - 50} 条连接)")

        return "\n".join(parts)

    @staticmethod
    def _find_nearest_text(
        x: float, y: float,
        text_grid: dict,
        x_min: float, y_min: float,
        grid_size: float,
        all_texts: list[TextEntity],
        search_radius: float = 50,
    ) -> str | None:
        """找给定坐标最近的文字"""
        gx = int((x - x_min) / grid_size)
        gy = int((y - y_min) / grid_size)

        candidates = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for txt in text_grid.get((gx + dx, gy + dy), []):
                    candidates.append(txt)

        if not candidates:
            return None

        # 找距离最近的（按网格内，不再做精细距离计算）
        # 优先返回非纯数字的文字
        for c in candidates:
            if not c.replace(".", "").replace("-", "").isdigit():
                return c

        return candidates[0] if candidates else None

    # ──────────────────────────────────────────────
    # AutoCAD COM 交互
    # ──────────────────────────────────────────────

    def _saveas_dxf(self, output_dir: str | None = None) -> str:
        """通过 AutoCAD COM SaveAs 导出 DXF"""
        import pythoncom
        pythoncom.CoInitialize()
        from config import settings
        import win32com.client

        acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
        doc = acad.ActiveDocument

        if not doc.FullName:
            raise RuntimeError("当前图纸未保存，无法导出 DXF")

        base = os.path.splitext(os.path.basename(doc.FullName))[0]
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            dxf_path = os.path.join(output_dir, f"{base}_extract.dxf")
        else:
            fd, dxf_path = tempfile.mkstemp(suffix=".dxf", prefix=f"{base}_")
            os.close(fd)

        doc.SaveAs(dxf_path, 37)
        file_size = os.path.getsize(dxf_path)
        logger.info(f"DXF saved for extraction: {dxf_path} ({file_size:,} bytes)")
        return dxf_path


# 全局单例
dxf_text_extractor = DXFTextExtractor()
