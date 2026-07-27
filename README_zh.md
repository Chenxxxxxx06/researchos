<!--
  ╔══════════════════════════════════════════════════════════════╗
  ║                    R E S E A R C H O S                      ║
  ║          AI-Native Research Operating System                ║
  ╚══════════════════════════════════════════════════════════════╝
-->

<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=36&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&random=false&width=600&lines=ResearchOS;AI+Research+Operating+System;%E5%AE%9E%E9%AA%8C++%E8%AE%BA%E6%96%87+++%E4%BB%A3%E7%A0%81;One+Workspace%2C+End+to+End" alt="ResearchOS" />

<p>
  <a href="https://github.com/NPUwho/researchos/actions/workflows/ci.yml"><img src="https://github.com/NPUwho/researchos/actions/workflows/ci.yml/badge.svg?label=CI" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue?style=flat&color=6366F1" alt="License" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white&color=3776AB" alt="Python" /></a>
  <a href="#"><img src="https://img.shields.io/badge/node-22+-green?logo=node.js&logoColor=white&color=339933" alt="Node" /></a>
  <a href="#"><img src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-361%20passed-success?logo=pytest&logoColor=white" alt="Tests" /></a>
  <a href="#"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen?logo=github&logoColor=white" alt="PRs Welcome" /></a>
</p>

<blockquote>
  <b>🔬 研究</b> · <b>💻 编码</b> · <b>🧪 实验</b> · <b>📝 写作</b><br/>
  一个工作台，端到端完成 AI 辅助科研全流程
</blockquote>

<p>
  <sub>Built with ❤️ using <b>FastAPI</b> + <b>Next.js</b> + <b>PostgreSQL/pgvector</b> + <b>Redis</b> + <b>Docker</b></sub>
</p>

</div>

---

<p align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="rainbow" />
</p>

## 🚀 30 秒快速启动

```bash
# 一行命令启动全部服务
pnpm stack:full

# 打开浏览器
open http://localhost:3000
```

| 🔑 Demo 账号 | |
|---|---|
| 邮箱 | `demo@researchos.dev` |
| 密码 | `demo-password-123` |

<p align="right">
  <sub><a href="#-手动安装">没有 pnpm？点这里 →</a></sub>
</p>

---

## 🎯 六大核心模块

<table>
<tr>
<td align="center" width="16%">
  <h3>🔍</h3>
  <b>Research Copilot</b>
</td>
<td width="50%">
  arXiv 论文搜索 · 个人图书馆 · 创意孵化 · LLM 对话 · 同行评审
</td>
<td width="34%">
  <sub>arXiv API · pgvector 语义检索 · Mock/Real LLM</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>🧠</h3>
  <b>AI IDE Workspace</b>
</td>
<td>
  文件树 · Monaco 编辑器 · Coding Agent · 可审查 Patch
</td>
<td>
  <sub>Monaco Editor · Git 版本控制 · Agent 驱动 Patch</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>🧪</h3>
  <b>Experiment Dashboard</b>
</td>
<td>
  实验管理 · 运行追踪 · Recharts 指标曲线 · 日志 · AI 分析
</td>
<td>
  <sub>Recharts 可视化 · 时序指标 · 实验对比</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>📄</h3>
  <b>Paper Workspace</b>
</td>
<td>
  三栏 LaTeX 编辑器 · AI 写作助手 · 实时预览
</td>
<td>
  <sub>LaTeX 编辑 · AI 辅助写作 · 编译预览</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>🧩</h3>
  <b>Skills Marketplace</b>
</td>
<td>
  5 个官方 Skill · 一键安装启用 · Skill Builder 自定义
</td>
<td>
  <sub>插件化架构 · 热加载 · 自定义 Skill</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>⚙️</h3>
  <b>Settings</b>
</td>
<td>
  中英文切换 · 项目级 LLM 配置 · OpenAI / Anthropic
</td>
<td>
  <sub>i18n · 多模型配置 · 项目隔离</sub>
</td>
</tr>
</table>

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│                     🖥️  Frontend                        │
│              Next.js 15 · React · Monaco                │
└──────────────────────┬──────────────────────────────────┘
                       │  REST / WebSocket
┌──────────────────────┴──────────────────────────────────┐
│                     ⚡ Backend                           │
│                   FastAPI · Celery                      │
│  ┌──────────┬──────────┬──────────┬──────────────┐     │
│  │ Research │  Coding  │Experiment│    Paper     │     │
│  │  Agent   │  Agent   │  Agent   │    Agent     │     │
│  └──────────┴──────────┴──────────┴──────────────┘     │
│               Agent Runtime · LLM Provider              │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────┐
│                     🗄️  数据层                           │
│       PostgreSQL (pgvector)  ·  Redis  ·  Docker        │
└─────────────────────────────────────────────────────────┘
```

---

## ⚡ 常用命令

| 🎯 命令 | 📝 说明 |
|---|---|
| `pnpm stack:full` | 完整重置：down → up → migrate → seed |
| `pnpm stack:up` | 启动全部服务 |
| `pnpm stack:down` | 停止全部服务 |
| `pnpm test` | 后端 pytest（361 测试） |
| `pnpm check` | 全质量门：test + typecheck + build |
| `pnpm smoke:api` | API 冒烟测试（16 端点） |
| `pnpm smoke:e2e` | Playwright E2E（10 页面） |

```bash
# Windows 用户也可以用 PowerShell
.\scripts\dev.ps1 full
.\scripts\dev.ps1 test
```

---

## 🚧 当前 Mock/Stub 状态

| 🔧 功能 | 📌 状态 |
|---|---|
| 🤖 LLM（无 API Key） | Mock 提供者（确定性、零成本）。Settings → LLM 配置真实 Key 后切换到 Anthropic / OpenAI |
| 📜 LaTeX 编译 | Mock 文本转换（无 shell、无 PDF）。真实隔离 latexmk 编译待实现 |
| 💻 终端面板 | 仅 UI 外壳（无命令执行） |
| 🌐 SSH 运行时 | 仅接口 + 权限模型（无远程连接） |
| 🧩 Skill 运行时注入 | Skills 可安装启用，Agent 运行时尚未注入 Skill prompt/workflow |

---

## 🗺️ 路线图

> 💡 *有想法？[发起 Discussion](https://github.com/NPUwho/researchos/discussions) 或提 PR！*

### 🔥 第一阶段 — 生产就绪（v0.2）

| 🎯 特性 | 📌 状态 |
|---|---|
| 🤖 真实 LLM 提供商（Anthropic Claude · OpenAI GPT · DeepSeek） | 🟡 计划中 |
| 📜 真实 LaTeX 编译（Docker 隔离 latexmk） | 🟡 计划中 |
| 🌿 Git 分支可视化 & 合并冲突解决 | 🟡 计划中 |
| 📊 实验指标对比（多轮并排展示） | 🟡 计划中 |
| 🔐 OAuth2 / SSO 登录（Google、GitHub、ORCID） | 🟡 计划中 |
| 📎 聊天文件上传 & 附件 | 🟡 计划中 |
| 🔔 实时通知（WebSocket 推送） | 🟡 计划中 |
| 🌓 暗色模式自动切换 | 🟡 计划中 |

### 🚀 第二阶段 — 协作（v0.3）

| 🎯 特性 | 📌 状态 |
|---|---|
| 👥 多人实时协作（Y.js CRDT） | ⚪ 待规划 |
| 💻 真实终端 & 沙箱执行（Firecracker/gVisor） | ⚪ 待规划 |
| 🌐 SSH 运行时 — 连接 HPC / 云 GPU / Slurm | ⚪ 待规划 |
| 📚 引用管理器集成（Zotero · Mendeley · Paperpile） | ⚪ 待规划 |
| 📑 PDF 标注 & 行内高亮 | ⚪ 待规划 |
| 🧪 自动化实验流水线（DAG 工作流） | ⚪ 待规划 |
| 📋 科研项目模板（计算机、生物、物理等） | ⚪ 待规划 |
| 🏷️ 论文自动标签 & 智能分类 | ⚪ 待规划 |

### 🌌 第三阶段 — 智能化（v1.0）

| 🎯 特性 | 📌 状态 |
|---|---|
| 🖼️ 多模态 Agent（图片、图表、表格、公式） | ⚪ 待规划 |
| 🔗 自动文献图谱 & 引用网络可视化 | ⚪ 待规划 |
| 📝 按会议/期刊自动排版（NeurIPS · ICML · ACL · Nature） | ⚪ 待规划 |
| ✅ 科研可复现性检查（重跑 + diff 输出） | ⚪ 待规划 |
| 🧩 社区 Skill 市场（发布 & 分享 Skill） | ⚪ 待规划 |
| 📈 学术影响力看板（引用、altmetrics、下载量） | ⚪ 待规划 |
| 🎙️ 语音转论文 & 会议总结 | ⚪ 待规划 |
| 🌍 跨源联合检索（arXiv · Semantic Scholar · PubMed · OpenAlex） | ⚪ 待规划 |
| 🧠 主动学习实验建议 | ⚪ 待规划 |
| 📦 一键论文到代码可复现包 | ⚪ 待规划 |

### 🧪 实验性 / 可能做

| 🎯 想法 | 💭 为什么 |
|---|---|
| 🎮 游戏化同行评审（评审对战、声誉积分） | 让评审有趣且有激励 |
| 🔮 研究方向预测器（来自 arXiv 的趋势预测） | 早期发现热门方向 |
| 🧬 Protocol.io / Protocols.io 集成 | 可复现湿实验方案 |
| 📊 实时会议看板（接收率、关键词趋势） | 会议季利器 |
| 🤝 "实验室搭子匹配" — 按研究兴趣找合作者 | 构建研究网络 |
| 🪄 "给 5 岁小孩讲这篇论文" — 分层摘要 | 科学传播 |
| 🔐 区块链时间戳研究声明 | 优先权 & 溯源 |
| 📱 移动 App — 随时检查实验 & 审批 Patch | 真正的随时随地访问 |
| 🎨 论文插图生成器（DALL·E / Stable Diffusion 集成） | 自动生成配图 |
| 🌐 自托管 arXiv 覆盖层（不离开 App 浏览批注） | 一站式工作流 |

---

## 👩‍💻 开发指南

### 🛠️ 环境要求

<p>
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/Node.js-22+-339933?logo=node.js&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/pnpm-9.15+-F69220?logo=pnpm&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/PostgreSQL-16+%2Bpgvector-4169E1?logo=postgresql&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/Redis-7+-DC382D?logo=redis&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/Git-required-F05032?logo=git&logoColor=white&style=flat-square" />
</p>

- conda 环境 `researchos`（conda-forge channel）
- corepack 启用：`corepack enable`

### 🧪 运行测试

```bash
cd apps/api

# 全部 361 测试
pytest -q

# 指定模块
pytest -q tests/test_coding_chat.py tests/test_git_service.py tests/test_patches.py

# 全质量门
pnpm check
```

---

## 📊 CI / 质量

<p align="center">
  <a href="https://github.com/NPUwho/researchos/actions/workflows/ci.yml"><img src="https://github.com/NPUwho/researchos/actions/workflows/ci.yml/badge.svg?label=CI%20Status" alt="CI" /></a>
</p>

GitHub Actions (`.github/workflows/ci.yml`) · push / PR 自动触发：

| 🧪 阶段 | ⚙️ 命令 | 🟢 状态 |
|---|---|---|
| Backend Lint | `ruff check .` + `mypy researchos` | ✅ |
| Backend Test | `pytest -q`（PostgreSQL + Redis，361 tests） | ✅ |
| Frontend Typecheck | `pnpm -r typecheck` | ✅ |
| Frontend Build | `pnpm --filter web build` | ✅ |

<details>
<summary>💡 CI 中的 Git 身份</summary>

测试提交的 git 身份通过 `GIT_AUTHOR_*` / `GIT_COMMITTER_*` 环境变量注入（配置在 `researchos/git/runner.py`），CI 环境无需 `~/.gitconfig`。
</details>

---

## 📚 文档导航

| 📖 文档 | 📝 说明 |
|---|---|
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | 运维指南 & 故障排除 |
| [`docs/MVP_STATUS.md`](docs/MVP_STATUS.md) | MVP 完成度追踪 |
| [`docs/SKILL_BUILDER.md`](docs/SKILL_BUILDER.md) | Skill 架构 & 开发指南 |
| [`docs/`](docs/) | 产品设计 · 数据库 · API 设计 |

---

## 🤝 参与贡献

我们欢迎一切形式的贡献！提 Issue、PR、或者直接在 Discussions 里聊想法。

<p align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="rainbow" />
</p>

<p align="center">
  <sub>Made with 🔬 by researchers, for researchers</sub><br/>
  <sub>© 2024–2026 ResearchOS · <a href="LICENSE">MIT License</a></sub>
</p>

---

<details>
<summary><b>📦 手动安装</b>（没有 pnpm 时使用）</summary>

```bash
# Docker 启动
docker compose -f infra/docker/docker-compose.yml up -d --build
docker compose -f infra/docker/docker-compose.yml exec -T api alembic upgrade head
docker compose -f infra/docker/docker-compose.yml exec -T api python -m researchos.seed.demo
```

```powershell
# Windows PowerShell
.\scripts\dev.ps1 full
```
</details>
