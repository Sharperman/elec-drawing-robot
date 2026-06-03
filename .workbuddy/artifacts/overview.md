# 视觉化图纸阅读 — 矢量图导出方案

## 问题现状

Lanczos 超分对工程图纸完全无效——线条和文字放大后锯齿更严重，LLM 无法识别。

## 根因诊断

经过深入排查，发现 AutoCAD 2021 的 **COM 类型库未注册到 Windows 系统**：

| 操作 | 结果 |
|------|------|
| `acad.Version` | ✅ `24.0s (LMS Tech)` |
| `acad.HWND` | ✅ `23268780` (int) |
| `doc.Name` | ❌ `AttributeError: <unknown>.Name` |
| `doc.ModelSpace.Count` | ❌ `AttributeError` |
| `doc.Export(tmp, 'BMP', None)` | ❌ `AttributeError` |
| `doc.Export(tmp, 'WMF', None)` | ❌ `AttributeError` |
| `doc.Plot.PlotToFile(...)` | ❌ `AttributeError` |

所有嵌套 COM 对象的方法全部失败，win32com 只能用 `CDispatch`（纯动态代理），在类型库缺失时无法解析嵌套对象。

## 解决方案

**安装 ODA File Converter**，用 `ezdxf` + `odafc` 读取 DWG 文件并导出 **SVG 矢量图**。

### 安装步骤

1. 下载 ODA File Converter（免费）：https://www.opendesign.com/guestfiles/oda_file_converter
2. 解压到任意目录（如 `C:\ODA\`）
3. 将 `ODAFileConverter.exe` 所在目录加入 PATH

### 代码改动

安装后将 `snapshot.py` 中的 `capture()` 方法增加矢量路径：

```
capture(mode='auto'):
  ├── mode='svg'  → ezdxf+odafc 读 DWG → SVG
  ├── mode='raster' → Win32 截图（现有逻辑）
  └── mode='auto' → 优先 SVG，fallback 截图
```

`visual_reader.py` 将 SVG 直接传给多模态 LLM（LLM 能理解 SVG 中的文字和图形）。

### 预期效果

- SVG 矢量图，任意缩放不失真
- 文字标注清晰可读
- LLM 能准确识别设备类型、参数、连接关系
- 3385 个图元的图纸导出 SVG 预计 5-20 MB

## 待执行

- [ ] 下载安装 ODA File Converter
- [ ] 更新 snapshot.py 增加 SVG 导出
- [ ] 更新 visual_reader.py 使用 SVG
- [ ] 重启后端验证
