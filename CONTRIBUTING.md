# 版本管理规范 (CONTRIBUTING.md)

> 适用于：电气图纸绘制机器人（elec-drawing-robot）  
> 当前版本：v1.0.0

---

## 一、分支策略

```
main          ← 稳定版本（仅接受 merge，不直接 push）
  └── develop ← 日常集成分支
        ├── feat/xxx    功能开发
        ├── fix/xxx     Bug 修复
        └── chore/xxx   配置/文档/依赖调整
```

| 分支 | 说明 | 允许直接 push |
|------|------|:---:|
| `main` | 生产版本，必须通过测试 | ❌ |
| `develop` | 日常集成 | ✅ |
| `feat/*` | 新功能开发 | ✅ |
| `fix/*` | Bug 修复 | ✅ |
| `chore/*` | 配置、文档、依赖 | ✅ |

### 工作流示例

```bash
# 开始新功能
git checkout develop
git checkout -b feat/voice-input

# 开发完成后合并回 develop
git checkout develop
git merge feat/voice-input --no-ff
git branch -d feat/voice-input

# 发布版本时合并到 main 并打标签
git checkout main
git merge develop --no-ff
git tag -a v1.1.0 -m "Release v1.1.0 — 语音输入支持"
```

---

## 二、提交信息规范（Conventional Commits）

格式：`<type>(<scope>): <subject>`

| type | 含义 | 示例 |
|------|------|------|
| `feat` | 新功能 | `feat(agent): 新增语音输入 ASR 集成` |
| `fix` | Bug 修复 | `fix(chat): 修复 updated_at 自赋值问题` |
| `refactor` | 重构（无新功能/无 Bug 修复）| `refactor(autocad): 提取连接池单例` |
| `test` | 新增/修改测试 | `test(recognition): 新增 YOLO 降级路径测试` |
| `docs` | 文档变更 | `docs: 更新 README 启动步骤` |
| `chore` | 构建/依赖/配置 | `chore: 锁定 langchain==0.2.16` |
| `perf` | 性能优化 | `perf(detector): 启动时预热 YOLO 模型` |

**scope**（可选，模块名）：`agent` / `autocad` / `recognition` / `knowledge` / `feedback` / `api` / `frontend` / `electron`

---

## 三、版本号规则（Semantic Versioning）

格式：`vMAJOR.MINOR.PATCH`

| 版本位 | 触发条件 | 示例 |
|--------|----------|------|
| MAJOR | 不兼容的 API 或架构变更 | v1→v2：废弃旧 COM 接口 |
| MINOR | 向后兼容的新功能（P1/P2 需求） | v1.0→v1.1：语音输入上线 |
| PATCH | Bug 修复 / 依赖升级 / 小优化 | v1.0.0→v1.0.1：修复标注缩放 |

### 打标签命令

```bash
# 正式版本
git tag -a v1.1.0 -m "Release v1.1.0 — 语音输入 + 厂家资料解析"

# 预发布版本（可选）
git tag -a v1.1.0-rc.1 -m "RC1: 待真实 AutoCAD 环境验证"

# 查看所有标签
git tag -l

# 查看某标签详情
git show v1.0.0
```

---

## 四、版本历史

| 版本 | 日期 | 变更摘要 |
|------|------|---------|
| **v1.0.0** | 2026-05-21 | MVP 初版：AutoCAD COM + LangChain Agent + 图元符号库 + Electron 桌面应用，151/151 测试通过 |

---

## 五、常用回溯命令

```bash
# 查看版本历史（图形化）
git log --oneline --graph --all

# 回到某个版本查看（不改变工作区）
git checkout v1.0.0

# 回到当前最新版本
git checkout main

# 比对两个版本的差异
git diff v1.0.0 v1.1.0 -- backend/agent/draw_agent.py

# 查看某文件的全部修改历史
git log --follow -p backend/api/routes/chat.py

# 回滚某一次提交（安全方式，生成新 commit）
git revert <commit-hash>

# 临时保存未提交的修改
git stash
git stash pop
```

---

## 六、需要特别记录的文件（版本间差异关键）

| 文件 | 说明 |
|------|------|
| `docs/PRD.md` | 需求变更时同步更新版本号 |
| `requirements.txt` | 每次依赖变更必须 commit，锁定精确版本 |
| `backend/knowledge/data/symbols/symbols.json` | 图元库扩充时记录新增符号 |
| `backend/knowledge/data/standards/default_standard.json` | 规范变更必须有对应 commit 说明 |
| `CHANGELOG.md` | 可选，记录面向用户的变更说明 |
