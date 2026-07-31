"""
日志查看 API
GET /api/logs/list    - 列出日志文件
GET /api/logs/view    - 查看日志内容（支持分页和过滤）
"""
from pathlib import Path

from config import settings
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()


class LogFileItem(BaseModel):
    name: str
    path: str
    size_bytes: int
    modified: str


class LogContent(BaseModel):
    file: str
    total_lines: int
    page: int
    page_size: int
    lines: list[str]
    has_more: bool


# ============================================================
# 列出日志文件
# ============================================================

@router.get("/list")
async def list_logs() -> dict:
    """列出所有日志文件"""
    log_dir = Path(settings.LOG_DIR)
    if not log_dir.exists():
        return {"code": 0, "data": []}

    files: list[LogFileItem] = []
    for f in sorted(log_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
        if f.is_file() and f.suffix in (".log", ".zip"):
            stat = f.stat()
            files.append(LogFileItem(
                name=f.name,
                path=str(f.relative_to(log_dir)),
                size_bytes=stat.st_size,
                modified=str(stat.st_mtime),
            ))

    return {"code": 0, "data": [item.model_dump() for item in files]}


# ============================================================
# 查看日志内容
# ============================================================

@router.get("/view")
async def view_log(
    file: str = Query(default="app.log", description="日志文件名"),
    level: str | None = Query(default=None, description="按级别过滤: DEBUG/INFO/WARNING/ERROR"),
    search: str | None = Query(default=None, description="搜索关键词"),
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=100, ge=10, le=500, description="每页行数"),
) -> dict:
    """查看日志文件内容，支持分页和级别/关键词过滤"""
    log_dir = Path(settings.LOG_DIR)

    # 安全校验：防止路径穿越
    file_path = (log_dir / file).resolve()
    if not str(file_path).startswith(str(log_dir.resolve())):
        raise HTTPException(status_code=403, detail="Invalid log file path")

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Log file not found: {file}")

    if file_path.suffix == ".zip":
        raise HTTPException(status_code=400, detail="Cannot view zipped log files directly")

    # 读取文件
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            raw_lines = [line.rstrip("\n") for line in f]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read log: {e}")

    # 过滤
    filtered = raw_lines
    if level:
        level_upper = level.upper()
        filtered = [l for l in filtered if f"| {level_upper: <8}" in l or f"| {level_upper} " in l]

    if search:
        search_lower = search.lower()
        filtered = [l for l in filtered if search_lower in l.lower()]

    # 分页（倒序：最新在前）
    total = len(filtered)
    reversed_lines = list(reversed(filtered))
    start = (page - 1) * page_size
    end = start + page_size
    page_lines = reversed_lines[start:end]

    return {
        "code": 0,
        "data": LogContent(
            file=file,
            total_lines=total,
            page=page,
            page_size=page_size,
            lines=page_lines,
            has_more=end < total,
        ).model_dump(),
    }
