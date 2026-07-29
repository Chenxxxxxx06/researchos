<!--
  ╔══════════════════════════════════════════════════════════════╗
  ║                    R E S E A R C H O S                      ║
  ║          AI-Native Research Operating System                ║
  ╚══════════════════════════════════════════════════════════════╝
-->

<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=36&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&random=false&width=600&lines=ResearchOS;AI+Research+Operating+System;%E5%AE%9E%E9%AA%8C+%E2%86%92+%E8%AE%BA%E6%96%87+%E2%86%92+%E4%BB%A3%E7%A0%81;One+Workspace%2C+End+to+End" alt="ResearchOS" />

<img src="docs/assets/researchos-otter.png" width="180" alt="ResearchOS 科研小獭 Rho" />

<p>
  <sub><b>这是 Rho，ResearchOS 的科研小獭。</b>保持好奇、善用工具，并认真把每条结论连接到证据。</sub>
</p>

<br/>

<p>
  <a href="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml"><img src="https://img.shields.io/badge/CI-passing-61E6B2?style=flat-square&logo=githubactions&logoColor=white" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-6366F1?style=flat-square" /></a>
  <a href="docs/TODO_ZH.md"><img src="https://img.shields.io/badge/maintenance-active-61E6B2?style=flat-square" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" /></a>
  <a href="#"><img src="https://img.shields.io/badge/node-22+-339933?style=flat-square&logo=nodedotjs&logoColor=white" /></a>
  <a href="#"><img src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" /></a>
  <a href="mailto:3653448612@qq.com"><img src="https://img.shields.io/badge/ideas-welcome-brightgreen?style=flat-square" /></a>
</p>

<br/>

> **🔬 研究** · **💻 编码** · **🧪 实验** · **📝 写作**
>
> 一个工作台，端到端完成 AI 辅助科研全流程。

<p>
  <sub>Built with FastAPI + Next.js + PostgreSQL/pgvector + Redis + Docker</sub>
</p>

</div>

---

## 🚀 快速启动

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

<br/>

### 终端 Harness（alpha）

```bash
cd apps/api && uv pip install -e .

researchos init
researchos register --email you@example.com --display-name "Your Name"
researchos login --email you@example.com
researchos projects create --name "My Research"
researchos use <project-id>
researchos ask "分析当前工作的创新点与实验缺口"
researchos chat
```

CLI 已支持真实 API 登录、项目选择、Agent Run、交互会话、科研记忆和 Mission 人工闸门骨架。

<details>
<summary><b>📦 手动安装（没有 pnpm）</b></summary>

```bash
docker compose -f infra/docker/docker-compose.yml up -d --build
docker compose -f infra/docker/docker-compose.yml exec -T api alembic upgrade head
docker compose -f infra/docker/docker-compose.yml exec -T api python -m researchos.seed.demo
```

```powershell
# Windows PowerShell
.\scripts\dev.ps1 full
```
</details>

---

## 🎯 核心工作台

<table>
<tr>
<td align="center" width="64"><h3>🔍</h3></td>
<td width="120"><b>Research Copilot</b></td>
<td>arXiv 论文搜索 · 个人图书馆 · 创意孵化 · LLM 对话 · 同行评审</td>
<td><sub>arXiv API · pgvector · Mock / Real LLM</sub></td>
</tr>
<tr>
<td align="center"><h3>🧠</h3></td>
<td><b>AI IDE</b></td>
<td>文件树 · Monaco 编辑器 · Coding Agent · 可审查 Patch</td>
<td><sub>Monaco · Git · Agent 驱动 Patch</sub></td>
</tr>
<tr>
<td align="center"><h3>🧪</h3></td>
<td><b>实验面板</b></td>
<td>实验管理 · 运行追踪 · Recharts 指标 · AI 分析</td>
<td><sub>Recharts · 时序指标 · 实验对比</sub></td>
</tr>
<tr>
<td align="center"><h3>📄</h3></td>
<td><b>论文工作台</b></td>
<td>三栏 LaTeX 编辑器 · AI 写作助手 · 实时预览</td>
<td><sub>LaTeX · AI 辅助写作 · 编译预览</sub></td>
</tr>
<tr>
<td align="center"><h3>⚙️</h3></td>
<td><b>设置</b></td>
<td>中英文切换 · 项目级 LLM 配置 · OpenAI / Anthropic</td>
<td><sub>i18n · 多模型 · 项目隔离</sub></td>
</tr>
</table>

---

## 🏗️ 架构

```
 ┌─────────────────────────────────────────────┐
 │              Frontend (Next.js 15)           │
 │         React · Monaco · Tailwind            │
 └──────────────────┬──────────────────────────┘
                    │  REST / WebSocket
 ┌──────────────────┴──────────────────────────┐
 │              Backend (FastAPI)               │
 │    Celery · Agent Runtime · LLM Provider     │
 │  ┌─────────┬─────────┬──────────┬────────┐  │
 │  │Research │ Coding  │Experiment│ Paper  │  │
 │  │ Agent   │ Agent   │  Agent   │ Agent  │  │
 │  └─────────┴─────────┴──────────┴────────┘  │
 └──────────────────┬──────────────────────────┘
                    │
 ┌──────────────────┴──────────────────────────┐
 │    PostgreSQL (pgvector) · Redis · MinIO     │
 └─────────────────────────────────────────────┘
```

---

## 🗺️ 能力路线图

详细状态与验收标准见 [docs/TODO_ZH.md](docs/TODO_ZH.md)。

| 能力 | 状态 |
|---|---|
| Zotero 文献同步、推荐入口、参考文献中心 | ✅ 可用骨架 |
| 多人归属树、Coordinator/子 Agent 协议 | ✅ 可用骨架 |
| Research Inbox：方向提取、会议总结、转写稿转论文 | ✅ / 🟡 |
| 真实受限本地终端、实验进度追踪 | ✅ 可用骨架 |
| CCFDDL 实时会议 DDL，iCal 搜索/筛选/订阅 | ✅ 可用骨架 |
| Reviewer Arena：真实 Agent Run、结构化 rubric | ✅ 可用骨架 |
| `researchos` / `ros` CLI、科研 Context、Mission scaffold | ✅ 可用骨架 |
| GitHub Pages 宣传站与 Tag Release 质量门 | ✅ 已部署 |
| PDF 标注、实验 DAG、多模态、引用图谱 | ⚪ 待实现 |
| SSH / HPC / Slurm、隔离任意命令、持续 Mission | ⚪ 待实现 |
| 断线持续执行、Server Lab、GPU 感知调度 | ⚪ 待实现 |
| Skill / System Prompt Registry、上下文压缩与评测 | ⚪ 待实现 |
| 社区 Skill / Prompt / Workflow Registry 与签名信任 | ⚪ 待实现 |
| Harness 执行适配器（Claude / Codex / OpenClaw / nanobot） | ⚪ 待实现 |
| Venue-aware Idea Gate、结构化 Reviewer 复审闭环 | ⚪ 待实现 |

---

## 🚧 Mock/Stub 状态

| 功能 | 状态 |
|---|---|
| 🤖 LLM（无 API Key） | Mock 提供者（零成本）。Settings → LLM 配置真实 Key |
| 📜 LaTeX 编译 | Mock 文本转换。真实隔离 latexmk 编译待实现 |
| 💻 终端面板 | 仅 local 环境执行真实 argv；只读 Git、目录边界、超时和输出上限 |
| 🌐 SSH 运行时 | 仅接口 + 权限模型（无远程连接） |
| 🎙️ 音频 | 转写稿分析可用；ASR、说话人分离、对象存储待实现 |

---

## ⚡ 常用命令

| 命令 | 说明 |
|---|---|
| `pnpm stack:full` | 完整重置：down → up → migrate → seed |
| `pnpm stack:up` | 启动全部服务 |
| `pnpm stack:down` | 停止全部服务 |
| `pnpm test` | 后端 pytest 测试套件 |
| `pnpm check` | 全质量门：test + typecheck + build |
| `pnpm smoke:api` | API 冒烟测试（16 端点） |
| `pnpm smoke:e2e` | 核心工作台 Playwright E2E |

```bash
# Windows PowerShell
.\scripts\dev.ps1 full
.\scripts\dev.ps1 test
```

---

## 👩‍💻 开发指南

### 环境要求

<p>
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Node.js-22+-339933?style=flat-square&logo=nodedotjs&logoColor=white" />
  <img src="https://img.shields.io/badge/pnpm-9.15+-F69220?style=flat-square&logo=pnpm&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16+%2Bpgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-7+-DC382D?style=flat-square&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white" />
</p>

- conda 环境 `researchos`（conda-forge）
- corepack 启用：`corepack enable`

### 运行测试

```bash
cd apps/api

pytest -q                          # 全部后端测试
pytest -q tests/test_coding_chat.py tests/test_git_service.py  # 指定模块
pnpm check                         # 全质量门
```

---

## 📊 CI

<p align="center">
  <a href="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml"><img src="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml/badge.svg?label=CI" alt="CI" /></a>
</p>

| 阶段 | 命令 | 状态 |
|---|---|---|
| Backend Lint | `ruff check .` + `mypy researchos` | ✅ |
| Backend Test | `pytest -q`（PostgreSQL + Redis） | ✅ |
| Frontend Typecheck | `pnpm -r typecheck` | ✅ |
| Frontend Build | `pnpm --filter web build` | ✅ |

---

## 📚 文档导航

| 文档 | 说明 |
|---|---|
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | 运维指南 & 故障排除 |
| [`docs/MVP_STATUS.md`](docs/MVP_STATUS.md) | MVP 完成度追踪 |
| [`docs/SKILL_BUILDER.md`](docs/SKILL_BUILDER.md) | Skill 架构 & 开发指南 |
| [`docs/`](docs/) | 产品设计 · 数据库 · API 设计 |

---

<br/>

<p align="center">
  <sub>Made with 🔬 by researchers, for researchers</sub><br/>
  <sub>© 2024–2026 Chenxxxxxx06 · <a href="LICENSE">保留所有权利</a></sub>
</p>
