# 电气图纸绘制机器人 (ElecDrawingRobot)

AI 驱动的电气图纸自动绘制系统，通过自然语言对话指令控制 AutoCAD 完成电气图纸绘制。

## 功能特性

- 自然语言指令 → AutoCAD 图纸绘制
- GB/T 4728 标准电气图元符号库
- YOLOv8 图片识别，自动解析电气元件
- 多轮对话上下文记忆
- 国标规范约束（图层/线型/颜色/字体）
- 用户反馈自学习（Feedback-Loop）

## 环境要求

| 组件 | 版本要求 |
|------|---------|
| Python | ≥ 3.10 |
| Node.js | ≥ 20 LTS |
| AutoCAD | 2020 ~ 2025（需安装并注册 COM） |
| Windows | 10/11 64-bit（pywin32 依赖） |
| CUDA（可选）| ≥ 11.8（YOLOv8 GPU 加速） |

## 目录结构

```
elec-drawing-robot/
├── backend/                 # Python FastAPI 后端
│   ├── main.py              # 应用入口
│   ├── config.py            # 配置管理
│   ├── models/              # ORM 模型
│   ├── api/                 # 路由 + Schema
│   ├── agent/               # LangChain Agent
│   ├── autocad/             # AutoCAD COM 操作
│   ├── knowledge/           # 知识库 + RAG
│   └── feedback/            # 反馈自学习
├── frontend/                # Electron + React 前端
│   ├── electron/            # 主进程
│   └── src/                 # 渲染进程 (React)
├── scripts/                 # 工具脚本
└── requirements.txt
```

## 快速启动

### 1. 安装依赖

```bat
scripts\install_deps.bat
```

### 2. 配置环境变量

复制 `.env.example` 并填写：

```bat
copy .env.example .env
```

编辑 `.env`：

```env
OPENAI_API_KEY=sk-xxxxxxxx
MODEL_NAME=gpt-4o
AUTOCAD_VERSION=AutoCAD.Application.25
```

### 3. 初始化数据库

```bat
python scripts\init_db.py
```

### 4. 启动后端

```bat
scripts\start_backend.bat
```

### 5. 启动前端（开发模式）

```bat
cd frontend
npm run dev
```

### 6. 打包 Electron 应用

```bat
cd frontend
npm run build
npm run dist
```

## AutoCAD 连接说明

1. 启动 AutoCAD 并打开一个图纸文件
2. 在应用中点击「连接 AutoCAD」按钮
3. 系统通过 COM（`win32com.client.Dispatch`）连接 AutoCAD 进程
4. 确保 AutoCAD 版本与 `AUTOCAD_VERSION` 配置一致

## API 文档

启动后端后访问：http://localhost:8765/docs

## 许可证

MIT License
