# ============================================================
# 电气图纸绘制机器人 — Backend Docker Image
# ============================================================
# Build:  docker build -t elec-drawing-robot-backend .
# Run:    docker run -p 8765:8765 --env-file .env elec-drawing-robot-backend
# ============================================================

ARG PYTHON_VERSION=3.12
FROM python:${PYTHON_VERSION}-slim-bookworm

LABEL org.opencontainers.image.title="ElecDrawingRobot Backend"
LABEL org.opencontainers.image.description="电气图纸绘制机器人 — FastAPI 后端 API 服务"
LABEL org.opencontainers.image.source="https://github.com/elec-drawing/elec-drawing-robot"

# System deps for opencv, chromadb, etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY backend/ ./backend/
COPY tests/ ./tests/
COPY pytest.ini .
COPY scripts/ ./scripts/

# Create data directory (runtime volume mount target)
RUN mkdir -p /app/backend/data

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health')" || exit 1

EXPOSE 8765

# NOTE: AutoCAD COM (pywin32) requires Windows — not available in this container.
# The container serves the API and knowledge base; CAD operations are proxied
# to a Windows host with AutoCAD installed.

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8765"]
