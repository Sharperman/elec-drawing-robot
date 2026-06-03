"""
AutoCAD 截图与矢量导出工具

策略：
- capture(): Win32 窗口截图（快速光栅图，用于常规场景）
- capture_vector(): DXF→SVG 矢量导出（永不模糊，白色线条自动转黑）
"""
import io
import os
import tempfile
import base64
from typing import Optional, Literal

from loguru import logger


# 超分目标宽度（None=不超分，使用原始窗口尺寸）
DEFAULT_UPSCALE_WIDTH = 3840  # 4K 宽度

# ACI 颜色常量
ACI_WHITE = 7
ACI_BYLAYER = 256
ACI_BYBLOCK = 0
ACI_BLACK_REPLACEMENT = 250  # 用于替换白色的深灰色（在白色背景上近似黑色）


class AutoCADSnapshot:
    """截取 AutoCAD 窗口截图 / 导出矢量图"""

    # ──────────────────────────────────────────────
    # 公开 API
    # ──────────────────────────────────────────────

    def capture(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        upscale: bool = True,
    ) -> str:
        """
        截取 AutoCAD 窗口光栅截图（PNG base64）

        Args:
            width: 目标宽度（像素），None 则自动计算
            height: 目标高度（像素），None 则自动计算
            upscale: 是否启用 Lanczos 超分（默认 True，4K 输出）

        Returns:
            PNG 截图的 base64 编码字符串（含 data URL 前缀）

        Raises:
            RuntimeError: 所有截图方法均失败
        """
        upscale_w = DEFAULT_UPSCALE_WIDTH if upscale else None

        # 方法一：Win32 窗口截图 + Lanczos 超分（最可靠）
        try:
            return self._capture_via_screenshot(width, height, upscale_w)
        except Exception as e:
            logger.warning(f"Win32 screenshot failed: {e}, trying COM Export")

        # 方法二：COM Export
        try:
            return self._capture_via_com(width, height, upscale_w)
        except Exception as e:
            logger.warning(f"COM Export failed: {e}, trying FindWindow fallback")

        # 方法三：FindWindow 兜底
        try:
            return self._capture_via_findwindow(width, height, upscale_w)
        except Exception as e:
            raise RuntimeError(f"所有截图方法均失败: {e}")

    def capture_vector(
        self,
        output_dir: Optional[str] = None,
        white_to_black: bool = True,
        dpi: int = 150,
    ) -> str:
        """
        矢量导出：AutoCAD SaveAs DXF → ezdxf 解析 → matplotlib 渲染 SVG

        流程：
        1. AutoCAD COM SaveAs → 临时 DXF 文件
        2. ezdxf 读取，将白色图元/图层颜色替换为深色
        3. matplotlib 渲染为 SVG（矢量，永不模糊）

        Args:
            output_dir: SVG 输出目录，None 则用系统临时目录
            white_to_black: 是否将白色线条转为深色（默认 True）
            dpi: 渲染 DPI（影响字体/线宽精度，不影响矢量本质）

        Returns:
            SVG 文件绝对路径

        Raises:
            RuntimeError: 导出失败
        """
        # 1. AutoCAD COM SaveAs DXF
        dxf_path = self._saveas_dxf(output_dir)

        try:
            # 2. ezdxf 读取 + 颜色修正 + 渲染 SVG
            svg_path = self._dxf_to_svg(
                dxf_path,
                white_to_black=white_to_black,
                dpi=dpi,
            )
            logger.info(f"Vector SVG exported: {svg_path}")
            return svg_path
        finally:
            # 清理临时 DXF
            try:
                os.unlink(dxf_path)
            except Exception:
                pass

    def capture_vector_base64(
        self,
        white_to_black: bool = True,
        dpi: int = 150,
    ) -> str:
        """
        矢量导出并返回 base64 data URL（方便直接传给 LLM 或前端）

        Args:
            white_to_black: 是否将白色线条转为深色
            dpi: 渲染 DPI

        Returns:
            data:image/svg+xml;base64,... 字符串
        """
        svg_path = self.capture_vector(
            white_to_black=white_to_black,
            dpi=dpi,
        )
        try:
            with open(svg_path, "rb") as f:
                svg_bytes = f.read()
            b64 = base64.b64encode(svg_bytes).decode("utf-8")
            return f"data:image/svg+xml;base64,{b64}"
        finally:
            try:
                os.unlink(svg_path)
            except Exception:
                pass

    # ──────────────────────────────────────────────
    # 矢量导出内部实现
    # ──────────────────────────────────────────────

    def _saveas_dxf(self, output_dir: Optional[str] = None) -> str:
        """通过 AutoCAD COM SaveAs 导出 DXF 临时文件"""
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client
        from config import settings

        acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
        doc = acad.ActiveDocument

        if not doc.FullName:
            raise RuntimeError("当前图纸未保存，无法导出 DXF")

        # 生成临时 DXF 路径
        base = os.path.splitext(os.path.basename(doc.FullName))[0]
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            dxf_path = os.path.join(output_dir, f"{base}_export.dxf")
        else:
            fd, dxf_path = tempfile.mkstemp(suffix=".dxf", prefix=f"{base}_")
            os.close(fd)

        # ac2018_DXF = 37
        doc.SaveAs(dxf_path, 37)
        file_size = os.path.getsize(dxf_path)
        logger.info(f"DXF saved: {dxf_path} ({file_size:,} bytes)")
        return dxf_path

    def _dxf_to_svg(
        self,
        dxf_path: str,
        white_to_black: bool = True,
        dpi: int = 150,
        line_width: float = 0,
    ) -> str:
        """
        ezdxf 读取 DXF → 分离文字/线条 → matplotlib 渲染 SVG

        核心策略（解决中文乱码）：
        1. ezdxf 只渲染非文字图元（线条、多段线、圆弧等）
        2. 文字实体用 matplotlib 原生 ax.text() 绘制 → 保留为 SVG <text> 元素
        3. 绕过 ezdxf 字体引擎，直接用系统 TTF 中文字体（Microsoft YaHei）
        """
        import ezdxf
        from ezdxf.addons.drawing import RenderContext, Frontend
        from ezdxf.addons.drawing.matplotlib import MatplotlibBackend
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        # 中文字体配置
        _setup_chinese_font()
        # 关键：SVG 里文字保持为原生 <text> 元素，不转为 path
        plt.rcParams["svg.fonttype"] = "none"

        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()

        # 先统计
        all_entities = list(msp)
        logger.info(f"DXF loaded: {len(all_entities)} entities, version={doc.dxfversion}")

        # 分离文字实体（在 destroy 之前先保存数据）
        text_entity_types = {"TEXT", "MTEXT", "ATTRIB", "ATTDEF"}
        saved_texts = []
        for e in all_entities:
            if e.dxftype() in text_entity_types:
                saved_texts.append(self._extract_text_data(e))
                e.destroy()
        logger.info(f"Text entities extracted & removed: {len(saved_texts)}")

        # 颜色/线宽转换
        if white_to_black:
            changed = self._convert_white_to_black(doc)
            logger.info(f"White→black conversion: {changed}")

        # ezdxf 渲染非文字图元（先用自动尺寸，后续根据数据范围调整）
        fig, ax = plt.subplots(figsize=(20, 15), dpi=dpi)
        ctx = RenderContext(doc)
        out = MatplotlibBackend(ax)
        Frontend(ctx, out).draw_layout(msp, finalize=True)

        # 获取 ezdxf 渲染后的数据范围，据此调整 figsize 保持宽高比
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        data_w = xlim[1] - xlim[0]
        data_h = ylim[1] - ylim[0]
        logger.info(f"DXF data range: {data_w:.0f} x {data_h:.0f}")

        if data_w > 0 and data_h > 0:
            aspect = data_w / data_h
            # 重新设置 figsize 匹配图纸比例
            if aspect > 1:
                fig.set_size_inches(24, 24 / aspect)
            else:
                fig.set_size_inches(24 * aspect, 24)

        # 手动绘制文字（matplotlib 原生 ax.text → SVG <text>）
        drawn = self._draw_texts_manual(ax, saved_texts)

        ax.set_aspect("equal")
        ax.axis("off")

        # 后处理：设置所有线条宽度
        if line_width is not None:
            for child in ax.get_children():
                import matplotlib.lines as mlines
                import matplotlib.collections as mcoll
                if isinstance(child, (mlines.Line2D,)):
                    child.set_linewidth(line_width)
                elif isinstance(child, mcoll.LineCollection):
                    child.set_linewidth(line_width)
                elif isinstance(child, mcoll.PatchCollection):
                    child.set_linewidth(line_width)

        svg_path = dxf_path.replace(".dxf", ".svg")
        fig.savefig(
            svg_path,
            format="svg",
            bbox_inches="tight",
            pad_inches=0.1,
            transparent=False,
            facecolor="white",
        )
        plt.close(fig)

        svg_size = os.path.getsize(svg_path)
        logger.info(f"SVG rendered: {svg_path} ({svg_size:,} bytes)")
        return svg_path

    @staticmethod
    def _extract_text_data(entity) -> dict:
        """从 ezdxf 文字实体提取渲染所需数据"""
        data = {
            "type": entity.dxftype(),
            "text": "",
            "x": 0.0,
            "y": 0.0,
            "height": 2.5,
            "rotation": 0.0,
            "color": 256,
        }

        # 文字内容
        if entity.dxftype() == "MTEXT":
            data["text"] = entity.plain_text() if hasattr(entity, "plain_text") else ""
        else:
            data["text"] = entity.dxf.text if hasattr(entity.dxf, "text") else ""

        # 插入点
        if hasattr(entity.dxf, "insert"):
            data["x"] = entity.dxf.insert.x
            data["y"] = entity.dxf.insert.y

        # 文字高度
        if hasattr(entity.dxf, "height"):
            data["height"] = entity.dxf.height

        # 旋转角度
        if hasattr(entity.dxf, "rotation"):
            data["rotation"] = entity.dxf.rotation

        # 颜色
        if hasattr(entity.dxf, "color"):
            data["color"] = entity.dxf.color

        return data

    @staticmethod
    def _draw_texts_manual(ax, saved_texts: list) -> int:
        """
        用 matplotlib 原生 ax.text() 绘制文字，返回绘制数量

        关键：文字大小需要根据 ax 的 data limits 与 figsize/dpi 的关系来缩放。
        DXF 文字高度（如 2.5）是 CAD 单位，需要映射为 matplotlib points。
        计算公式：fontsize_pt = cad_height * (fig_width_inches * dpi) / data_width
        """
        if not saved_texts:
            return 0

        # 获取 ezdxf 渲染后的实际坐标范围
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()
        data_width = xlim[1] - xlim[0]
        data_height = ylim[1] - ylim[0]

        if data_width <= 0 or data_height <= 0:
            logger.warning("ax data limits are zero/negative, skipping text draw")
            return 0

        # 获取 figure 尺寸和 dpi，计算 data→points 缩放因子
        fig = ax.figure
        fig_w_in, fig_h_in = fig.get_size_inches()
        dpi = fig.get_dpi()

        # 每个 data 单位对应多少 points
        # 使用较小的缩放因子确保文字不会太大
        scale_x = (fig_w_in * dpi) / data_width
        scale_y = (fig_h_in * dpi) / data_height
        scale = min(scale_x, scale_y)

        drawn = 0
        for t in saved_texts:
            text = str(t["text"]).strip()
            if not text:
                continue

            x, y = t["x"], t["y"]
            h = t["height"]
            rot = t["rotation"]

            # 跳过明显在可视范围外的文字
            margin = data_width * 0.1
            if (x < xlim[0] - margin or x > xlim[1] + margin or
                    y < ylim[0] - margin or y > ylim[1] + margin):
                continue

            # 字体大小：CAD 文字高度 × 缩放因子 = points
            fontsize = h * scale
            # 限制在合理范围
            fontsize = max(3, min(48, fontsize))

            # 颜色：全部黑色（用户要求）
            color = "black"

            ax.text(
                x, y, text,
                fontsize=fontsize,
                rotation=rot,
                ha="left",
                va="baseline",
                color=color,
                clip_on=False,
            )
            drawn += 1

        logger.info(
            f"Manual text drawn: {drawn}/{len(saved_texts)} "
            f"(scale={scale:.2f} pt/unit, data={data_width:.0f}x{data_height:.0f})"
        )
        return drawn

    @staticmethod
    def _convert_white_to_black(doc) -> int:
        """
        将 DXF 中所有白色/浅色图元转为深色

        处理策略：
        1. 图层颜色为 ACI 7（白色）→ 改为 ACI 250（深灰≈黑色）
        2. 实体显式颜色为 ACI 7 → 改为 ACI 250
        3. ByLayer(256) 图元通过图层颜色间接处理（步骤1已覆盖）

        Returns:
            修改的实体+图层总数
        """
        import ezdxf

        changed = 0

        # 1. 改图层颜色
        for layer in doc.layers:
            if layer.dxf.color == ACI_WHITE:
                layer.dxf.color = ACI_BLACK_REPLACEMENT
                changed += 1

        # 2. 改实体显式颜色
        for entity in doc.modelspace():
            try:
                if entity.dxf.color == ACI_WHITE:
                    entity.dxf.color = ACI_BLACK_REPLACEMENT
                    changed += 1
            except Exception:
                pass

        return changed

    # ──────────────────────────────────────────────
    # Win32 窗口截图（原有方法，保持不变）
    # ──────────────────────────────────────────────

    @staticmethod
    def _get_acad_hwnd(acad) -> int:
        """获取 AutoCAD 主窗口句柄"""
        try:
            raw = acad.HWND
        except Exception as e:
            raise RuntimeError(f"无法获取 AutoCAD HWND: {e}") from e

        if isinstance(raw, int):
            return raw

        for attr in ("Value", "value", "__int__", "int"):
            try:
                val = getattr(raw, attr, None)
                if callable(val):
                    val = val()
                if isinstance(val, int) and val > 0:
                    return val
            except Exception:
                pass

        try:
            return int(raw)
        except (ValueError, TypeError):
            pass

        raise RuntimeError(
            f"AutoCAD HWND 类型无法解析: {type(raw).__name__} = {raw!r}"
        )

    @staticmethod
    def _ensure_window_visible(hwnd: int) -> tuple[int, int]:
        """确保 AutoCAD 窗口在可见区域，返回 (width, height)"""
        import win32gui
        import win32con

        rect = win32gui.GetWindowRect(hwnd)
        x, y = rect[0], rect[1]
        w, h = rect[2] - rect[0], rect[3] - rect[1]

        if x < -2000 or y < -2000 or w < 200 or h < 200:
            logger.warning(
                f"AutoCAD window off-screen ({x},{y} {w}x{h}), repositioning..."
            )
            target_w = max(w, 1200)
            target_h = max(h, 800)
            win32gui.SetWindowPos(
                hwnd, 0, 0, 0, target_w, target_h,
                win32con.SWP_NOZORDER | win32con.SWP_SHOWWINDOW,
            )
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            import time
            time.sleep(0.5)
            rect = win32gui.GetWindowRect(hwnd)
            w = rect[2] - rect[0]
            h = rect[3] - rect[1]
            logger.info(f"Window repositioned: {w}x{h}")

        return w, h

    def _capture_via_com(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        upscale_width: Optional[int] = None,
    ) -> str:
        """通过 AutoCAD COM Export 导出"""
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client
        from config import settings
        from PIL import Image

        acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
        doc = acad.ActiveDocument

        formats_to_try = ["PNG", "BMP", "WMF"]
        last_error = None

        for fmt in formats_to_try:
            fd, tmp_path = tempfile.mkstemp(suffix=f".{fmt.lower()}")
            os.close(fd)

            try:
                try:
                    doc.Export(tmp_path, fmt, None)
                except Exception as e:
                    last_error = e
                    continue

                file_size = os.path.getsize(tmp_path)
                if file_size == 0:
                    last_error = RuntimeError(f"Export {fmt} 生成空文件")
                    continue

                try:
                    img = Image.open(tmp_path)
                    img.load()
                except Exception as e:
                    last_error = RuntimeError(f"Export {fmt} 无法打开: {e}")
                    continue

                logger.info(f"AutoCAD Export {fmt} OK: {file_size} bytes, {img.size}")
                return self._finalize_image(img, width, height, upscale_width)

            finally:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

        raise RuntimeError(f"COM Export 失败（已尝试 {formats_to_try}）: {last_error}")

    def _capture_via_screenshot(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        upscale_width: Optional[int] = None,
    ) -> str:
        """通过 Win32 API 截取 AutoCAD 窗口"""
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client
        from config import settings

        acad = win32com.client.GetActiveObject(settings.AUTOCAD_VERSION)
        hwnd = self._get_acad_hwnd(acad)
        return self._capture_window(hwnd, width, height, upscale_width)

    def _capture_via_findwindow(
        self,
        width: Optional[int] = None,
        height: Optional[int] = None,
        upscale_width: Optional[int] = None,
    ) -> str:
        """通过 FindWindow 查找 AutoCAD 窗口"""
        import win32gui

        hwnd = None
        for class_name in (
            "Afx:0000000140000000:0",
            "Afx:0000000140000000",
            "AfxFrameOrView140",
            "AfxMDIFrame140u",
        ):
            try:
                hwnd = win32gui.FindWindow(class_name, None)
                if hwnd:
                    break
            except Exception:
                pass

        if not hwnd:
            def _callback(h, _):
                try:
                    if "AutoCAD" in win32gui.GetWindowText(h):
                        return False, h
                except Exception:
                    pass
                return True, None
            try:
                _, hwnd = win32gui.EnumWindows(lambda h, _: _callback(h, _), None)
            except Exception:
                pass

        if not hwnd:
            raise RuntimeError("无法找到 AutoCAD 窗口（所有查找方式均失败）")

        return self._capture_window(hwnd, width, height, upscale_width)

    def _capture_window(
        self,
        hwnd: int,
        width: Optional[int] = None,
        height: Optional[int] = None,
        upscale_width: Optional[int] = None,
    ) -> str:
        """通用的 Win32 窗口截图 + 可选 Lanczos 超分"""
        import win32gui
        import win32ui
        import win32con
        from PIL import Image

        win_w, win_h = self._ensure_window_visible(hwnd)

        if win_w <= 0 or win_h <= 0:
            raise RuntimeError(f"AutoCAD 窗口尺寸无效: {win_w}x{win_h}")

        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        save_bitmap = win32ui.CreateBitmap()
        save_bitmap.CreateCompatibleBitmap(mfc_dc, win_w, win_h)
        save_dc.SelectObject(save_bitmap)
        save_dc.BitBlt((0, 0), (win_w, win_h), mfc_dc, (0, 0), win32con.SRCCOPY)

        bmp_info = save_bitmap.GetInfo()
        bmp_data = save_bitmap.GetBitmapBits(True)

        img = Image.frombuffer(
            "RGB",
            (bmp_info["bmWidth"], bmp_info["bmHeight"]),
            bmp_data,
            "raw",
            "BGRX",
            0,
            1,
        )

        win32gui.DeleteObject(save_bitmap.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)

        logger.info(f"Win32 capture: {img.size}")
        return self._finalize_image(img, width, height, upscale_width)

    def _finalize_image(
        self,
        img,
        width: Optional[int] = None,
        height: Optional[int] = None,
        upscale_width: Optional[int] = None,
    ) -> str:
        """最终化图片：可选缩放 + 可选 Lanczos 超分 → base64 PNG"""
        from PIL import Image, ImageEnhance

        if width and height:
            img = img.resize((width, height), Image.LANCZOS)

        if upscale_width and upscale_width > img.size[0]:
            ratio = upscale_width / img.size[0]
            target_h = int(img.size[1] * ratio)
            img = img.resize((upscale_width, target_h), Image.LANCZOS)

            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(1.2)
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.05)

            logger.info(f"Lanczos upscaled to: {img.size}")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        b64 = base64.b64encode(buffer.read()).decode("utf-8")
        return f"data:image/png;base64,{b64}"


def _setup_chinese_font():
    """配置 matplotlib 中文字体，按优先级选择可用的中文字体"""
    import matplotlib
    from matplotlib import font_manager as fm

    # 候选字体（按优先级）
    _CANDIDATE_FONTS = [
        "Microsoft YaHei",
        "SimHei",
        "Noto Sans SC",
        "STXihei",
        "Microsoft JhengHei",
        "SimSun",
        "KaiTi",
        "FangSong",
    ]

    # 重建字体缓存（确保新安装字体可被发现）
    try:
        fm._load_fontmanager(try_read_cache=False)
    except Exception:
        pass

    available = {f.name for f in fm.fontManager.ttflist}

    for font_name in _CANDIDATE_FONTS:
        if font_name in available:
            matplotlib.rcParams["font.sans-serif"] = [font_name, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            logger.debug(f"Chinese font set to: {font_name}")
            return

    logger.warning("No Chinese font found, text may render as boxes")


# 全局单例
autocad_snapshot = AutoCADSnapshot()
