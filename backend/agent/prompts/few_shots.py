"""
Few-Shot 示例
自然语言指令 → Tool 调用链示例，用于引导 LLM 正确使用工具
"""

# ============================================================
# Few-Shot 示例集（自然语言 → 工具调用链）
# ============================================================

FEW_SHOT_EXAMPLES = [
    # ---- 示例 1：插入变压器 ----
    {
        "user": "在坐标 (100, 200) 处插入一个 10kV/0.4kV 的变压器，命名为 T1",
        "thoughts": "用户要插入一台双绕组变压器，symbol_id=TR_2W，位置(100,200)，需要添加标注 T1 和 10kV/0.4kV",
        "tool_calls": [
            {
                "tool": "insert_element",
                "args": {
                    "symbol_id": "TR_2W",
                    "x": 100.0,
                    "y": 200.0,
                    "rotation": 0.0,
                    "layer": "ELEC-TRANSFORMER",
                    "label": "T1",
                },
                "result": "图块 TR_2W 插入成功，Handle=3A8",
            },
            {
                "tool": "add_annotation",
                "args": {
                    "handle": "3A8",
                    "label": "T1",
                    "params": "10kV/0.4kV",
                    "position": "bottom",
                },
                "result": "标注 T1 / 10kV/0.4kV 添加成功",
            },
        ],
        "assistant": "已在坐标 (100, 200) 插入 T1 变压器，参数标注 10kV/0.4kV。",
    },
    # ---- 示例 2：绘制三相断路器 + 连接母线 ----
    {
        "user": "在变压器 T1 上方 20mm 处插入三相断路器 QF1，并用 10kV 母线将它们连接起来",
        "thoughts": (
            "需要先查询 T1 的位置，然后在其上方 20mm 插入断路器，最后绘制连线。"
        ),
        "tool_calls": [
            {
                "tool": "query_drawing",
                "args": {"filter_label": "T1"},
                "result": "找到图元 T1: handle=3A8, x=100.0, y=200.0",
            },
            {
                "tool": "insert_element",
                "args": {
                    "symbol_id": "CB_3P",
                    "x": 100.0,
                    "y": 226.0,
                    "layer": "ELEC-PROTECT",
                    "label": "QF1",
                },
                "result": "图块 CB_3P 插入成功，Handle=3B2",
            },
            {
                "tool": "draw_connection",
                "args": {
                    "from_handle": "3B2",
                    "to_handle": "3A8",
                    "line_type": "bus",
                    "layer": "ELEC-BUS",
                },
                "result": "连接线绘制成功，Handle=3C1",
            },
            {
                "tool": "add_annotation",
                "args": {
                    "handle": "3B2",
                    "label": "QF1",
                    "params": "630A",
                    "position": "right",
                },
                "result": "标注 QF1 / 630A 添加成功",
            },
        ],
        "assistant": "已插入断路器 QF1(630A) 并与 T1 变压器通过母线连接。",
    },
    # ---- 示例 3：查询当前图纸 ----
    {
        "user": "现在图纸上有哪些设备？",
        "thoughts": "用户询问当前图纸状态，使用 query_drawing 工具获取所有图元列表",
        "tool_calls": [
            {
                "tool": "query_drawing",
                "args": {},
                "result": (
                    "ModelSpace 共 5 个图元：\n"
                    "1. T1 (TR_2W) at (100,200) layer=ELEC-TRANSFORMER\n"
                    "2. QF1 (CB_3P) at (100,226) layer=ELEC-PROTECT\n"
                    "3. 母线 at (100,220) layer=ELEC-BUS\n"
                    "4. 标注 T1 at (100,192)\n"
                    "5. 标注 QF1 at (105,226)"
                ),
            }
        ],
        "assistant": (
            "当前图纸中有 5 个图元：\n"
            "- **T1**（双绕组变压器）：位于 (100, 200)\n"
            "- **QF1**（三相断路器）：位于 (100, 226)\n"
            "- 母线连接线：连接 QF1 与 T1\n"
            "- 2 个设备标注"
        ),
    },
    # ---- 示例 4：识别图片 ----
    {
        "user": "[上传图片] 请帮我识别这张图里有哪些电气元件",
        "thoughts": "用户上传了图片并要求识别，需调用图像识别功能",
        "tool_calls": [],
        "assistant": (
            "我已收到图片，正在进行 YOLOv8 电气元件识别...\n\n"
            "识别结果：\n"
            "1. 断路器 (CB_3P) - 置信度 92%，位置左上区域\n"
            "2. 变压器 (TR_2W) - 置信度 88%，位置中央\n"
            "3. 接地符号 (GND) - 置信度 95%，位置右下\n\n"
            "是否需要将识别到的元件自动插入到 AutoCAD 中？"
        ),
    },
    # ---- 示例 5：修改图层配置 ----
    {
        "user": "将 ELEC-BUS 图层的颜色改为红色（颜色索引 1），线宽改为 0.7mm",
        "thoughts": "用户要修改图层属性，使用 modify_element 工具修改图层配置",
        "tool_calls": [
            {
                "tool": "modify_element",
                "args": {
                    "target_type": "layer",
                    "target_name": "ELEC-BUS",
                    "properties": {
                        "color_index": 1,
                        "lineweight": 0.7,
                    },
                },
                "result": "图层 ELEC-BUS 颜色已更新为 1（红色），线宽 0.7mm",
            }
        ],
        "assistant": "已将 ELEC-BUS 图层颜色修改为红色（颜色索引 1），线宽设为 0.7mm。",
    },
]


def format_few_shots_for_prompt() -> str:
    """
    将 Few-Shot 示例格式化为提示词文本

    Returns:
        格式化的示例字符串
    """
    parts = ["# 示例操作参考\n"]
    for i, example in enumerate(FEW_SHOT_EXAMPLES, 1):
        parts.append(f"## 示例 {i}")
        parts.append(f"**用户**：{example['user']}")
        parts.append(f"**助手思考**：{example['thoughts']}")
        parts.append(f"**助手回复**：{example['assistant']}")
        parts.append("")
    return "\n".join(parts)
