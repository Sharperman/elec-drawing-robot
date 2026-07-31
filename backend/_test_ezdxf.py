"""测试 ezdxf 读取 DWG 并导出 SVG"""
from collections import Counter
import os
import time

import ezdxf
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.svg import SVGBackend
from ezdxf.bbox import extents as bbox_extents

dwg_path = r'C:\Users\li_hk\Desktop\HQ1595F-7D2-1-风电场电气主接线图-20260305.dwg'

print(f'Reading: {dwg_path}')
t0 = time.time()

dwg = ezdxf.readfile(dwg_path)
msp = dwg.modelspace()
entities = list(msp)
print(f'Entities: {len(entities)} ({time.time()-t0:.1f}s)')

# 统计类型
types = Counter(e.dxftype() for e in entities)
print(f'Types: {dict(types)}')

# 范围
try:
    bbox = bbox_extents(msp)
    print(f'Extents: {bbox.extmin} -> {bbox.extmax}')
except Exception as e:
    print(f'Bbox: {e}')

# 导出 SVG
svg_path = '/tmp/acad_drawing.svg'
t0 = time.time()

with open(svg_path, 'w', encoding='utf-8') as f:
    backend = SVGBackend(f)
    frontend = Frontend(RenderContext(dwg), backend)
    frontend.draw_layout(msp, finalize=True)

svg_size = os.path.getsize(svg_path)
print(f'SVG: {svg_size/1024:.1f} KB ({time.time()-t0:.1f}s)')

# 读 SVG 转 base64 data URI
with open(svg_path, encoding='utf-8') as f:
    svg_content = f.read()

# 用 data URI（非 base64，直接内联）
data_uri = 'data:image/svg+xml,' + svg_content.replace('#', '%23').replace('\n', '')
print(f'Data URI length: {len(data_uri)}')
print('SVG preview (first 500 chars):')
print(svg_content[:500])
