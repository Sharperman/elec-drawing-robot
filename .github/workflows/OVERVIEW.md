# CI/CD 工作流实施报告

## 项目：电气图纸绘制机器人 (elec-drawing-robot)

---

## 创建的文件

### GitHub Actions 工作流（3个）

| 文件 | 触发条件 | 用途 |
|------|----------|------|
| `.github/workflows/ci.yml` | push/PR to main,develop | 后端 pytest + ruff + 前端 typecheck + build + 集成烟雾测试 |
| `.github/workflows/release.yml` | tag v*.*.* | 质量门 → 三平台 Electron 构建 → GitHub Release 自动发布 |
| `.github/workflows/deploy-staging.yml` | push to develop | 前端 Pages 预览 + 后端 Docker 镜像 + 预发布构建 |

### 支撑文件（5个）

| 文件 | 用途 |
|------|------|
| `Dockerfile` | 后端 FastAPI 容器化（python:3.12-slim，含 opencv/chromadb 系统依赖） |
| `.dockerignore` | 排除 node_modules/\_\_pycache\_\_/数据库/IDE 等构建无关文件 |
| `Makefile` | 跨平台开发命令：install/test/lint/format/build/dev/docker |
| `ruff.toml` | Python lint 规则：E/F/W/I/N/UP/B/C4/SIM/TCH/RUF |
| `.github/changelog-config.json` | Release 变更日志自动生成配置 |

### 修改的文件

| 文件 | 变更 |
|------|------|
| `pytest.ini` | 新增 [coverage:run] 和 [coverage:report] 配置段 |

---

## CI 流水线详解

```
push/PR → ci.yml
  ├─ backend (matrix: py3.12, py3.13)
  │   ├─ ruff lint
  │   ├─ mypy type check (non-blocking)
  │   └─ pytest + coverage (skip CAD tests)
  ├─ frontend (node22)
  │   ├─ TypeScript typecheck
  │   └─ Vite build
  ├─ integration (smoke test)
  │   └─ Start backend → health check → verify APIs
  └─ gate (final)
      └─ All gates passed/failed
```

## Release 流水线详解

```
tag v* → release.yml
  ├─ quality-gate (run full tests)
  ├─ build-windows (electron-builder NSIS)
  ├─ build-macos (electron-builder DMG, no code sign)
  ├─ build-linux (electron-builder AppImage)
  └─ github-release
      ├─ Auto-generate changelog from PRs
      └─ Create Release + attach all artifacts
```

## 需要配置的 Secrets

| Secret | 用途 | 必需？ |
|--------|------|--------|
| `OPENAI_API_KEY` | CI 测试中的 LLM Mock | 否（有 fallback `sk-test`） |
| `CODECOV_TOKEN` | 上传覆盖率到 Codecov | 否 |
| `STAGING_API_URL` (Variable) | 前端预览指向的 API 地址 | 否（默认 `/api`） |

## 注意事项

1. **AutoCAD 依赖**：CI 中所有 CAD 相关测试标记为跳过（`-k "not autocad and not cad and not com"`），因为 GitHub Runner 无 AutoCAD 环境。完整测试需在 Windows + AutoCAD 环境下运行。
2. **macOS 签名**：Release 构建关闭了 CSC_IDENTITY_AUTO_DISCOVERY，发布到 App Store 前需配置 Developer ID 证书。
3. **GitHub Pages**：staging 部署需要仓库 Settings → Pages → Source: GitHub Actions。
4. **GHCR**：Docker 镜像推送到 ghcr.io，需要仓库启用 Packages 权限。
5. **覆盖率门禁**：CI 设 `--cov-fail-under=60`，当前作为预警阈值，可根据实际覆盖率调整。
