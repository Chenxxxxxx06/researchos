<!--
  ╔══════════════════════════════════════════════════════════════╗
  ║                    R E S E A R C H O S                      ║
  ║          AI-Native Research Operating System                ║
  ╚══════════════════════════════════════════════════════════════╝
-->

<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=36&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&random=false&width=600&lines=ResearchOS;AI+Research+Operating+System;%E5%AE%9E%E9%AA%8C++%E8%AE%BA%E6%96%87+++%E4%BB%A3%E7%A0%81;One+Workspace%2C+End+to+End" alt="ResearchOS" />

<p>
  <a href="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml"><img src="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml/badge.svg?label=CI" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-6366F1?style=flat" alt="Proprietary License" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white&color=3776AB" alt="Python" /></a>
  <a href="#"><img src="https://img.shields.io/badge/node-22+-green?logo=node.js&logoColor=white&color=339933" alt="Node" /></a>
  <a href="#"><img src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-quality%20gated-blue?logo=pytest&logoColor=white" alt="Tests" /></a>
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

> 一体化科研闭环、Agent 协议、SSH/实验编排边界与能力完成标准见
> [产品与工程蓝图](docs/PRODUCT_BLUEPRINT_ZH.md)、[Agent 协议](docs/AGENT_PROTOCOL_ZH.md)
> 和[能力 TODO](docs/TODO_ZH.md)。

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

### 终端 Harness（alpha）

```bash
cd apps/api
uv pip install -e .

researchos init
researchos register --email you@example.com --display-name "Your Name"
researchos login --email you@example.com
researchos projects
researchos projects create --name "My Research"
researchos use <project-id>
researchos ask "分析当前工作的创新点与实验缺口"
researchos chat
```

CLI 已支持真实 API 登录、项目选择、Agent Run、交互会话、科研记忆、Context
Manifest、Mission 人工闸门骨架和外部 Harness 发现。详细设计见
[CLI 与科研记忆](docs/HARNESS_CLI_MEMORY_ZH.md)。

<p align="right">
  <sub><a href="#-手动安装">没有 pnpm？点这里 →</a></sub>
</p>

---

## 🎯 核心工作台

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
| `pnpm test` | 后端 pytest 测试套件 |
| `pnpm check` | 全质量门：test + typecheck + build |
| `pnpm smoke:api` | API 冒烟测试（16 端点） |
| `pnpm smoke:e2e` | 核心工作台 Playwright E2E |

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
| 💻 终端面板 | 仅 local 环境执行真实 argv；固定开发命令和只读 Git，带目录边界、超时和输出上限；生产环境强制关闭 |
| 🌐 SSH 运行时 | 仅接口 + 权限模型（无远程连接） |
| 🎙️ 音频 | 当前保存文件来源并分析转写稿；真实 ASR、说话人分离和对象存储待实现 |

---

## 🗺️ 能力路线图（不按阶段包装）

完整状态、边界和验收方式见 [docs/TODO_ZH.md](docs/TODO_ZH.md)。当前重点包括：

| 能力 | 当前状态 |
|---|---|
| Zotero 文献同步、推荐入口、独立参考文献中心 | ✅ 可用骨架 |
| LLM 配置连通性测试、创新点/下一步提取 | ✅ 可用骨架 |
| 多人归属树、Coordinator/子 Agent 协议 | ✅ 可用骨架 |
| Research Inbox：方向提取、会议总结、转写稿转论文 | ✅ / 🟡 |
| 真实受限本地终端、Git 只读状态 | ✅ 可用骨架 |
| 实验进度、数据输入流概览 | ✅ 可用骨架 |
| CCFDDL 实时会议 DDL、模拟 Reviewer | ✅ 可用骨架 |
| 项目页 / README / Poster Release Agent | ✅ 可用骨架 |
| PDF 标注、实验 DAG、自动标签、多模态、引用图谱、venue 排版、重跑 diff | ⚪ 待实现 |
| SSH/HPC/Slurm、隔离任意命令、持续 Research Mission | ⚪ 待实现 |
| `researchos` / `ros` CLI、科研 Context 与 Mission scaffold | ✅ 可用骨架 |
| Claude / Codex / OpenClaw / nanobot 执行适配器 | ⚪ 待实现（当前只发现并链接） |
| GitHub Pages 宣传页与 Tag Release 质量门 | ✅ 可用骨架 |

> 功能等你来提供想法！欢迎发送场景、输入输出和验收方式到
> [3653448612@qq.com](mailto:3653448612@qq.com)。

## 🙏 设计参考与致谢

- [academic-research-skills](https://github.com/Imbad0202/academic-research-skills)：科研流水线、材料护照和多人交接。
- [superpowers](https://github.com/obra/superpowers)：需求澄清、worktree、计划执行和双重审查。
- [Dify](https://github.com/langgenius/dify)：可视化工作流、模型编排与可观测性。
- [agent-skills](https://github.com/addyosmani/agent-skills)：DEFINE → PLAN → BUILD → VERIFY → REVIEW → SHIP。
- [nature-skills](https://github.com/Yuan1z0825/nature-skills)：论文、图表、审稿与展示工作流。
- [CCFA-Skills](https://github.com/mikubaka88/CCFA-Skills)：artifact owner、共享配置与投稿流水线。
- [ccf-deadlines](https://github.com/ccfddl/ccf-deadlines)：会议数据与 iCal 订阅来源。
- [CS Paper Review](https://cspaper.org/)：venue-aware 模拟评审交互参考。
- [LabVLA](https://zjunlp.github.io/LabVLA/) 与 [DiffBIR](https://0x3f3f3f3fun.github.io/projects/diffbir/)：项目宣传页信息结构参考。
- [Claude Code](https://code.claude.com/docs/en/how-claude-code-works)、[OpenAI Codex](https://github.com/openai/codex)、[OpenClaw](https://github.com/openclaw/openclaw) 与 [nanobot](https://github.com/HKUDS/nanobot)：Harness、CLI、会话、工具、网关和上下文管理参考；未直接复制其实现。

## 📖 新增设计文档

- [ResearchOS Harness、CLI 与科研记忆设计](docs/HARNESS_CLI_MEMORY_ZH.md)
- [科研教育 Harness 建设手册](docs/RESEARCH_EDUCATION_HARNESS_ROADMAP_ZH.md)
- [统一宣传文案包](docs/PROMOTION_COPY_ZH.md)
- [GitHub Pages 宣传站](https://chenxxxxxx06.github.io/researchos/)

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

# 全部后端测试
pytest -q

# 指定模块
pytest -q tests/test_coding_chat.py tests/test_git_service.py tests/test_patches.py

# 全质量门
pnpm check
```

---

## 📊 CI / 质量

<p align="center">
  <a href="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml"><img src="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml/badge.svg?label=CI%20Status" alt="CI" /></a>
</p>

GitHub Actions (`.github/workflows/ci.yml`) · push / PR 自动触发：

| 🧪 阶段 | ⚙️ 命令 | 🟢 状态 |
|---|---|---|
| Backend Lint | `ruff check .` + `mypy researchos` | ✅ |
| Backend Test | `pytest -q`（PostgreSQL + Redis） | ✅ |
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

## 🔒 项目归属与贡献

ResearchOS 为 **Chenxxxxxx06** 所有的专有项目。获得源码访问权限不代表获得复制、传播、
商业化、再授权或提供托管服务的许可。任何贡献均须事先获得授权并另行签署书面贡献协议。
具体条款见 [LICENSE](LICENSE) 与 [NOTICE.md](NOTICE.md)。

<p align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="rainbow" />
</p>

<p align="center">
  <sub>Made with 🔬 by researchers, for researchers</sub><br/>
  <sub>© 2024–2026 Chenxxxxxx06 · <a href="LICENSE">保留所有权利</a></sub>
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
