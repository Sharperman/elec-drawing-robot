"""
审查报告生成器

将 Agent 审查结果 + DXF 文本提取 + 规范知识库 合成为结构化 HTML 报告。
报告保存在图纸同文件夹下，文件名为 "{图名}-图纸审查.html"
"""

import json
import os
import re
from datetime import datetime
from typing import Optional

from loguru import logger


class ReviewReportGenerator:
    """
    图纸审查报告 HTML 生成器
    
    用法：
        gen = ReviewReportGenerator()
        html_path = gen.generate(
            review_result=agent_review_json,
            dxf_text=dxf_extracted_text,
            standards_context=standards_text,
            drawing_path="/path/to/drawing.dwg",
        )
    """

    def generate(
        self,
        review_result: dict,
        dxf_text: str = "",
        standards_context: str = "",
        drawing_path: str = "",
    ) -> str:
        """
        生成审查报告 HTML
        
        Args:
            review_result: Agent 审查结果 (dict with keys: drawing_info, devices, 
                           topology, checks, summary)
            dxf_text: DXF 结构化文本提取结果
            standards_context: 规范知识库上下文
            drawing_path: 图纸文件路径（用于确定报告保存位置和图纸名称）
            
        Returns:
            生成的 HTML 报告文件路径
        """
        # 确定图名和保存路径
        if drawing_path and os.path.exists(drawing_path):
            base_dir = os.path.dirname(drawing_path)
            drawing_name = os.path.splitext(os.path.basename(drawing_path))[0]
        else:
            base_dir = os.getcwd()
            drawing_name = review_result.get("drawing_info", {}).get("drawing_name", "未命名图纸")
        
        report_name = f"{drawing_name}-图纸审查.html"
        report_path = os.path.join(base_dir, report_name)
        
        # 构建 HTML
        html = self._build_html(review_result, dxf_text, standards_context, drawing_name)
        
        # 写入文件
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(html)
        
        logger.info(f"Review report generated: {report_path}")
        return report_path

    def _build_html(
        self,
        review_result: dict,
        dxf_text: str,
        standards_context: str,
        drawing_name: str,
    ) -> str:
        """构建 HTML 内容"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 解析各部分数据
        drawing_info = review_result.get("drawing_info", {})
        devices = review_result.get("devices", [])
        topology = review_result.get("topology", "")
        checks = review_result.get("checks", [])
        summary = review_result.get("summary", {})
        
        # 严重程度统计
        severity_count = {"error": 0, "warning": 0, "info": 0, "pass": 0}
        for c in checks:
            result = c.get("result", "").lower()
            if "通过" in result or "pass" in result:
                severity_count["pass"] += 1
            elif "不通过" in result or "fail" in result:
                severity_count["error"] += 1
            elif "改进" in result or "warn" in result:
                severity_count["warning"] += 1
            else:
                severity_count["info"] += 1
        
        total_checks = len(checks)
        pass_rate = (severity_count["pass"] / total_checks * 100) if total_checks > 0 else 0
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{drawing_name} - 图纸审查报告</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    line-height: 1.6;
    padding: 2rem;
  }}
  .container {{ max-width: 1100px; margin: 0 auto; }}
  
  /* 头部 */
  .header {{
    background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
    border: 1px solid #334155;
    border-radius: 16px;
    padding: 2rem;
    margin-bottom: 1.5rem;
  }}
  .header h1 {{ font-size: 1.75rem; color: #f1f5f9; margin-bottom: 0.5rem; }}
  .header .meta {{
    display: flex; gap: 2rem; flex-wrap: wrap;
    color: #94a3b8; font-size: 0.875rem; margin-top: 1rem;
  }}
  .header .meta span {{ display: flex; align-items: center; gap: 0.375rem; }}
  .badge {{
    display: inline-block; padding: 0.25rem 0.75rem; border-radius: 999px;
    font-size: 0.75rem; font-weight: 600;
  }}
  .badge-pass {{ background: #065f46; color: #6ee7b7; }}
  .badge-warn {{ background: #78350f; color: #fcd34d; }}
  .badge-error {{ background: #7f1d1d; color: #fca5a5; }}
  .badge-info {{ background: #1e3a5f; color: #93c5fd; }}
  
  /* 概览卡片 */
  .summary-cards {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem; margin-bottom: 1.5rem;
  }}
  .summary-card {{
    background: #1e293b; border: 1px solid #334155; border-radius: 12px;
    padding: 1.25rem; text-align: center;
  }}
  .summary-card .number {{ font-size: 2rem; font-weight: 700; }}
  .summary-card .label {{ font-size: 0.8rem; color: #64748b; margin-top: 0.25rem; }}
  .summary-card.total .number {{ color: #93c5fd; }}
  .summary-card.pass .number {{ color: #6ee7b7; }}
  .summary-card.warn .number {{ color: #fcd34d; }}
  .summary-card.error .number {{ color: #fca5a5; }}
  
  /* 通过率进度条 */
  .pass-rate-bar {{
    height: 8px; background: #334155; border-radius: 4px;
    margin: 1rem 0; overflow: hidden;
  }}
  .pass-rate-fill {{
    height: 100%; border-radius: 4px; transition: width 0.6s ease;
    background: linear-gradient(90deg, #22c55e, #16a34a);
  }}
  
  /* 通用卡片 */
  .card {{
    background: #1e293b; border: 1px solid #334155; border-radius: 12px;
    padding: 1.5rem; margin-bottom: 1.5rem;
  }}
  .card h2 {{
    font-size: 1.125rem; color: #e2e8f0;
    padding-bottom: 0.75rem; margin-bottom: 1rem;
    border-bottom: 1px solid #334155;
  }}
  .card h3 {{
    font-size: 0.95rem; color: #cbd5e1; margin: 1rem 0 0.5rem;
  }}
  
  /* 图纸信息表 */
  .info-grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 0.75rem;
  }}
  .info-item {{
    display: flex; justify-content: space-between;
    padding: 0.5rem 0.75rem; background: #0f172a;
    border-radius: 6px; font-size: 0.875rem;
  }}
  .info-item .key {{ color: #64748b; }}
  .info-item .val {{ color: #e2e8f0; font-weight: 500; }}
  
  /* 设备表格 */
  table {{
    width: 100%; border-collapse: collapse; font-size: 0.875rem;
  }}
  th {{
    text-align: left; padding: 0.625rem 0.75rem;
    background: #0f172a; color: #64748b; font-weight: 600;
    border-bottom: 2px solid #334155;
  }}
  td {{
    padding: 0.5rem 0.75rem; border-bottom: 1px solid #1e293b;
  }}
  tr:hover td {{ background: #1e293b; }}
  
  /* 审查项列表 */
  .check-item {{
    display: flex; align-items: flex-start; gap: 0.75rem;
    padding: 0.875rem; margin-bottom: 0.5rem;
    background: #0f172a; border-radius: 8px;
    border-left: 4px solid #334155;
  }}
  .check-item.result-pass {{ border-left-color: #22c55e; }}
  .check-item.result-warn {{ border-left-color: #eab308; }}
  .check-item.result-error {{ border-left-color: #ef4444; }}
  .check-item.result-info {{ border-left-color: #3b82f6; }}
  .check-item.result-na {{ border-left-color: #475569; }}
  
  .check-icon {{ font-size: 1.25rem; flex-shrink: 0; margin-top: 0.125rem; }}
  .check-body {{ flex: 1; }}
  .check-title {{ font-weight: 600; font-size: 0.9rem; color: #e2e8f0; }}
  .check-rule {{ font-size: 0.75rem; color: #64748b; margin: 0.25rem 0; }}
  .check-detail {{ font-size: 0.8rem; color: #94a3b8; margin-top: 0.375rem; }}
  .check-suggestion {{
    font-size: 0.8rem; color: #fcd34d; margin-top: 0.375rem;
    padding: 0.375rem 0.5rem; background: rgba(234, 179, 8, 0.1);
    border-radius: 4px;
  }}
  
  /* 拓扑描述 */
  .topology-block {{
    background: #0f172a; border-radius: 8px; padding: 1rem;
    font-size: 0.875rem; white-space: pre-wrap; color: #94a3b8;
    max-height: 300px; overflow-y: auto;
  }}
  
  /* 总结 */
  .summary-section {{
    background: linear-gradient(135deg, #1e293b 0%, #1a2332 100%);
    border: 1px solid #334155; border-radius: 12px; padding: 1.5rem;
    margin-bottom: 1.5rem;
  }}
  .summary-section h2 {{ color: #f1f5f9; margin-bottom: 0.75rem; }}
  .summary-text {{ color: #94a3b8; font-size: 0.9rem; line-height: 1.8; }}
  
  /* 底部 */
  .footer {{
    text-align: center; color: #475569; font-size: 0.75rem;
    padding: 2rem 0 1rem;
  }}

  /* 滚动条 */
  ::-webkit-scrollbar {{ width: 6px; }}
  ::-webkit-scrollbar-track {{ background: #0f172a; }}
  ::-webkit-scrollbar-thumb {{ background: #334155; border-radius: 3px; }}
</style>
</head>
<body>
<div class="container">

<!-- 头部 -->
<div class="header">
  <h1>📋 {drawing_name} — 图纸审查报告</h1>
  <div class="meta">
    <span>📅 审查时间: {now}</span>
    <span>📐 图纸类型: {drawing_info.get('drawing_type', '未识别')}</span>
    <span>⚡ 电压等级: {drawing_info.get('voltage_level', '未标注')}</span>
    <span>📏 完整度: {drawing_info.get('completeness', '未知')}</span>
  </div>
  <div class="pass-rate-bar">
    <div class="pass-rate-fill" style="width: {pass_rate:.0f}%"></div>
  </div>
  <div style="text-align:right; font-size:0.8rem; color:#64748b;">审查通过率: {pass_rate:.0f}% ({severity_count['pass']}/{total_checks})</div>
</div>

<!-- 概览统计 -->
<div class="summary-cards">
  <div class="summary-card total">
    <div class="number">{total_checks}</div>
    <div class="label">总检查项</div>
  </div>
  <div class="summary-card pass">
    <div class="number">{severity_count['pass']}</div>
    <div class="label">✅ 通过</div>
  </div>
  <div class="summary-card warn">
    <div class="number">{severity_count['warning']}</div>
    <div class="label">⚠️ 需改进</div>
  </div>
  <div class="summary-card error">
    <div class="number">{severity_count['error']}</div>
    <div class="label">❌ 不通过</div>
  </div>
</div>
"""
        
        # ── 图纸基本信息 ──
        html += """
<!-- 图纸基本信息 -->
<div class="card">
  <h2>📐 图纸基本信息</h2>
  <div class="info-grid">
"""
        info_fields = [
            ("图纸名称", drawing_info.get("drawing_name", drawing_name)),
            ("图纸类型", drawing_info.get("drawing_type", "未识别")),
            ("项目名称", drawing_info.get("project_name", "未标注")),
            ("电压等级", drawing_info.get("voltage_level", "未标注")),
            ("图纸编号", drawing_info.get("drawing_number", "未标注")),
            ("绘图比例", drawing_info.get("scale", "未标注")),
            ("设计阶段", drawing_info.get("design_stage", "未标注")),
            ("设备总数", str(len(devices)) if devices else "0"),
            ("文字标注数", str(drawing_info.get("text_count", "0"))),
        ]
        for key, val in info_fields:
            html += f'    <div class="info-item"><span class="key">{key}</span><span class="val">{val}</span></div>\n'
        
        html += "  </div>\n</div>\n"
        
        # ── 设备清单 ──
        if devices:
            html += """
<!-- 设备清单 -->
<div class="card">
  <h2>🔌 设备清单</h2>
  <table>
    <thead><tr><th>#</th><th>设备类型</th><th>编号/名称</th><th>规格参数</th><th>数量</th><th>位置</th></tr></thead>
    <tbody>
"""
            for i, dev in enumerate(devices, 1):
                dtype = dev.get("type", dev.get("device_type", "未知"))
                label = dev.get("label", dev.get("name", "-"))
                spec = dev.get("spec", dev.get("specification", "-"))
                count = dev.get("count", 1)
                position = dev.get("position", "-")
                html += f'      <tr><td>{i}</td><td>{dtype}</td><td>{label}</td><td>{spec}</td><td>{count}</td><td>{position}</td></tr>\n'
            
            html += "    </tbody>\n  </table>\n</div>\n"
        
        # ── 系统拓扑 ──
        if topology:
            html += f"""
<!-- 系统拓扑 -->
<div class="card">
  <h2>🔗 系统拓扑</h2>
  <div class="topology-block">{topology}</div>
</div>
"""
        
        # ── 审查结果 ──
        if checks:
            # 按分类分组
            categories_order = ["完整性", "规范性", "一致性", "安全性"]
            grouped: dict[str, list] = {}
            for c in checks:
                cat = c.get("category", "其他")
                grouped.setdefault(cat, []).append(c)
            
            for cat in categories_order:
                if cat not in grouped:
                    continue
                items = grouped[cat]
                
                html += f"""
<!-- {cat}检查 -->
<div class="card">
  <h2>{self._category_icon(cat)} {cat}检查 ({len(items)} 项)</h2>
"""
                for item in items:
                    result = item.get("result", "")
                    rule_id = item.get("rule_id", "")
                    title = item.get("title", item.get("check_item", "未命名"))
                    detail = item.get("detail", item.get("description", ""))
                    suggestion = item.get("suggestion", "")
                    gb_ref = item.get("gb_ref", "")
                    
                    result_class = self._result_class(result)
                    result_icon = self._result_icon(result)
                    
                    html += f"""  <div class="check-item result-{result_class}">
    <div class="check-icon">{result_icon}</div>
    <div class="check-body">
      <div class="check-title">{title}</div>
"""
                    if rule_id or gb_ref:
                        ref_parts = []
                        if rule_id: ref_parts.append(rule_id)
                        if gb_ref: ref_parts.append(gb_ref)
                        html += f'      <div class="check-rule">📎 {" | ".join(ref_parts)}</div>\n'
                    
                    if detail:
                        html += f'      <div class="check-detail">{detail}</div>\n'
                    
                    if suggestion:
                        html += f'      <div class="check-suggestion">💡 建议: {suggestion}</div>\n'
                    
                    html += "    </div>\n  </div>\n"
                
                html += "</div>\n"
        
        # ── 总体评价 ──
        overall = summary.get("overall", summary.get("conclusion", ""))
        suggestions = summary.get("suggestions", summary.get("recommendations", []))
        issues = summary.get("issues", summary.get("problems", []))
        
        if overall or suggestions or issues:
            html += """
<!-- 总体评价 -->
<div class="summary-section">
  <h2>📝 总体评价</h2>
"""
            if overall:
                html += f'  <div class="summary-text">{overall}</div>\n'
            
            if issues:
                html += '  <h3 style="color:#fca5a5;">⚠️ 发现的问题</h3>\n  <ul style="color:#94a3b8; font-size:0.875rem; line-height:1.8; padding-left:1.5rem;">\n'
                for issue in issues:
                    html += f'    <li>{issue}</li>\n'
                html += '  </ul>\n'
            
            if suggestions:
                html += '  <h3 style="color:#6ee7b7;">💡 改进建议</h3>\n  <ul style="color:#94a3b8; font-size:0.875rem; line-height:1.8; padding-left:1.5rem;">\n'
                for sug in suggestions:
                    html += f'    <li>{sug}</li>\n'
                html += '  </ul>\n'
            
            html += "</div>\n"
        
        # ── 规范引用 ──
        if standards_context:
            # 提取规范编号
            refs = set()
            for m in re.finditer(r'GB[/\s]\d+[\.\d]*|NB/T\s*\d+[\.\d]*|DL/T\s*\d+[\.\d]*|IEC\s*\d+', standards_context):
                refs.add(m.group())
            
            if refs:
                html += """
<!-- 引用规范 -->
<div class="card">
  <h2>📚 引用规范</h2>
  <div class="info-grid">
"""
                for ref in sorted(refs):
                    html += f'    <div class="info-item"><span class="key">📄</span><span class="val">{ref}</span></div>\n'
                html += "  </div>\n</div>\n"
        
        # ── 底部 ──
        html += f"""
<div class="footer">
  <p>报告由 电气图纸审查系统 自动生成 | {now}</p>
  <p>本报告基于电气规范知识库和 AI 分析生成，仅供参考，最终审查结论以人工复核为准。</p>
</div>

</div>
</body>
</html>"""
        
        return html

    @staticmethod
    def _category_icon(category: str) -> str:
        icons = {
            "完整性": "📋",
            "规范性": "📏",
            "一致性": "🔗",
            "安全性": "🛡️",
        }
        return icons.get(category, "📌")

    @staticmethod
    def _result_class(result: str) -> str:
        r = result.lower()
        if "通过" in r or "pass" in r or "✅" in r:
            return "pass"
        elif "不通过" in r or "fail" in r or "❌" in r:
            return "error"
        elif "改进" in r or "warn" in r or "⚠️" in r:
            return "warn"
        elif "不适用" in r or "n/a" in r:
            return "na"
        return "info"

    @staticmethod
    def _result_icon(result: str) -> str:
        r = result.lower()
        if "通过" in r or "pass" in r:
            return "✅"
        elif "不通过" in r or "fail" in r:
            return "❌"
        elif "改进" in r or "warn" in r:
            return "⚠️"
        elif "不适用" in r or "n/a" in r:
            return "➖"
        return "🔵"


# 全局单例
review_report_generator = ReviewReportGenerator()
