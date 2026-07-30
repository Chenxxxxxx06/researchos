<!--
  ╔══════════════════════════════════════════════════════════════╗
  ║                    R E S E A R C H O S                      ║
  ║          AI-Native Research Operating System                ║
  ╚══════════════════════════════════════════════════════════════╝
-->

<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=36&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&random=false&width=600&lines=ResearchOS;AI+Research+Operating+System;Experiment+%E2%86%92+Paper+%E2%86%92+Code;One+Workspace%2C+End+to+End" alt="ResearchOS" />

<img src="docs/assets/researchos-otter.png" width="180" alt="Rho, the ResearchOS research otter" />

<p>
  <sub><b>Rho, the Research Otter.</b> Curious, tool-using, and serious about connecting every claim to its evidence.</sub>
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

> **🔬 Research** · **💻 Code** · **🧪 Experiment** · **📝 Write**
>
> One workspace, end-to-end AI-assisted research — from idea to paper.

<p>
  <sub>Built with FastAPI + Next.js + PostgreSQL/pgvector + Redis + Docker</sub>
</p>

<p>
  <a href="README_zh.md">📖 中文文档</a>
</p>

</div>

---

## 🚀 Quick Start

```bash
# One command. Everything running.
pnpm stack:full

# Open browser
open http://localhost:3000
```

| 🔑 Demo Account | |
|---|---|
| Email | `demo@researchos.dev` |
| Password | `demo-password-123` |

<br/>

### Terminal Harness (alpha)

```bash
cd apps/api && uv pip install -e .

researchos init
researchos register --email you@example.com --display-name "Your Name"
researchos login --email you@example.com
researchos projects create --name "My Research"
researchos use <project-id>
researchos ask "Find the innovation and experiment gaps"
researchos chat
```

CLI with real API auth, project selection, Agent Runs, interactive sessions, provenance-aware memory, and Mission approval scaffold.

<details>
<summary><b>📦 Manual Setup (no pnpm)</b></summary>

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

## 🎯 Workspaces

<table>
<tr>
<td align="center" width="64"><h3>🔍</h3></td>
<td width="120"><b>Research Copilot</b></td>
<td>arXiv search · Personal library · Idea incubation · LLM chat · Peer review</td>
<td><sub>arXiv API · pgvector · Mock / Real LLM</sub></td>
</tr>
<tr>
<td align="center"><h3>🧠</h3></td>
<td><b>AI IDE</b></td>
<td>File tree · Monaco editor · Coding Agent · Reviewable patches</td>
<td><sub>Monaco · Git · Agent-driven patches</sub></td>
</tr>
<tr>
<td align="center"><h3>🧪</h3></td>
<td><b>Experiments</b></td>
<td>Experiment management · Run tracking · Recharts metrics · AI analysis</td>
<td><sub>Recharts · Time-series · Side-by-side comparison</sub></td>
</tr>
<tr>
<td align="center"><h3>📄</h3></td>
<td><b>Paper Workspace</b></td>
<td>Three-panel LaTeX editor · AI writing assistant · Live preview</td>
<td><sub>LaTeX · AI-assisted writing · Compile & preview</sub></td>
</tr>
<tr>
<td align="center"><h3>⚙️</h3></td>
<td><b>Settings</b></td>
<td>ZH/EN toggle · Per-project LLM config · OpenAI / Anthropic</td>
<td><sub>i18n · Multi-model · Project isolation</sub></td>
</tr>
</table>

---

## 🦦 Looking for Collaborators

ResearchOS is at alpha — the skeleton works, but there's **way too much**
for one person. If any of these interest you, **let's build together:**

| Skill | What You'll Work On |
|---|---|
| React / Next.js | UI polish, workspace components, responsive layout |
| Python / FastAPI | API endpoints, agent tools, experiment analysis |
| DevOps / Docker | Container sandbox, CI/CD, deployment pipeline |
| LaTeX / Compilers | Real LaTeX compilation service, template system |
| Testing | E2E (Playwright), backend (pytest), integration tests |
| Docs / Content | Tutorials, README translations, video walkthroughs |
| ML / Agent Systems | Agent runtime, skills system, LLM provider adapters |

**Why contribute?**
- Real full-stack project — FastAPI + Next.js + PostgreSQL + Redis
- Code review and architecture discussions
- Strong resume item: _"built core modules for an open-source research OS"_
- Every PR gets reviewed and merged with your name in the history

→ **[Good First Issues](https://github.com/Chenxxxxxx06/researchos/issues)**

📧 3653448612@qq.com — reach out directly, happy to chat.

---

## 🏗️ Architecture

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

## 🗺️ Roadmap

See [docs/TODO_ZH.md](docs/TODO_ZH.md) for detailed acceptance criteria and boundaries.

| Capability | Status |
|---|---|
| Zotero center, LLM connection test, innovation extraction | ✅ usable skeleton |
| Coordinator/worker agent protocol, ownership tree | ✅ usable skeleton |
| Research Inbox: direction, meetings, transcript-to-paper | ✅ / 🟡 |
| Restricted real terminal, experiment progress tracking | ✅ usable skeleton |
| Live CCFDDL deadlines, iCal search/filter/subscription | ✅ usable skeleton |
| Reviewer Arena: real Agent Run, structured rubric | ✅ usable skeleton |
| `researchos` / `ros` CLI, scientific context, Mission scaffold | ✅ usable skeleton |
| GitHub Pages site + tag-release quality gate | ✅ deployed |
| PDF annotation, experiment DAG, multimodal, citation graph | ⚪ backlog |
| SSH / HPC / Slurm, arbitrary command isolation, continuous Mission | ⚪ backlog |
| Disconnect-safe execution, Server Lab, GPU-aware scheduling | ⚪ backlog |
| Skill / System Prompt registry, context compaction, evaluations | ⚪ backlog |
| Signed community Skill / Prompt / Workflow registry | ⚪ backlog |
| Harness execution adapters (Claude / Codex / OpenClaw / nanobot) | ⚪ backlog |
| Venue-aware idea gate, structured reviewer revision loop | ⚪ backlog |

---

## 🚧 Mock/Stub Status

| Feature | Status |
|---|---|
| 🤖 LLM (no API key) | Mock provider (zero-cost). Configure real key in Settings → LLM |
| 📜 LaTeX compilation | Mock text transform. Sandboxed latexmk planned |
| 💻 Terminal panel | Real argv in `local` only; read-only Git, cwd guard, timeout, output cap |
| 🌐 SSH runtime | Interface + permission model only |
| 🎙️ Audio | Transcript analysis works; ASR, diarization, object storage not yet |

---

## ⚡ Commands

| Command | Description |
|---|---|
| `pnpm stack:full` | Full reset: down → up → migrate → seed |
| `pnpm stack:up` | Start all services |
| `pnpm stack:down` | Stop all services |
| `pnpm test` | Backend pytest suite |
| `pnpm check` | Full quality gate: test + typecheck + build |
| `pnpm smoke:api` | API smoke test (16 endpoints) |
| `pnpm smoke:e2e` | Playwright E2E for core workspaces |

```bash
# Windows PowerShell
.\scripts\dev.ps1 full
.\scripts\dev.ps1 test
```

---

## 👩‍💻 Development

### Requirements

<p>
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Node.js-22+-339933?style=flat-square&logo=nodedotjs&logoColor=white" />
  <img src="https://img.shields.io/badge/pnpm-9.15+-F69220?style=flat-square&logo=pnpm&logoColor=white" />
  <img src="https://img.shields.io/badge/PostgreSQL-16+%2Bpgvector-4169E1?style=flat-square&logo=postgresql&logoColor=white" />
  <img src="https://img.shields.io/badge/Redis-7+-DC382D?style=flat-square&logo=redis&logoColor=white" />
  <img src="https://img.shields.io/badge/Git-F05032?style=flat-square&logo=git&logoColor=white" />
</p>

- conda environment `researchos` (conda-forge)
- corepack enabled: `corepack enable`

### Running Tests

```bash
cd apps/api

pytest -q                          # Full backend suite
pytest -q tests/test_coding_chat.py tests/test_git_service.py  # Specific modules
pnpm check                         # Full quality gate
```

---

## 📊 CI

<p align="center">
  <a href="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml"><img src="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml/badge.svg?label=CI" alt="CI" /></a>
</p>

| Stage | Command | Status |
|---|---|---|
| Backend Lint | `ruff check .` + `mypy researchos` | ✅ |
| Backend Test | `pytest -q` (PostgreSQL + Redis) | ✅ |
| Frontend Typecheck | `pnpm -r typecheck` | ✅ |
| Frontend Build | `pnpm --filter web build` | ✅ |

---

## 📚 Docs

| Document | Description |
|---|---|
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Ops guide & troubleshooting |
| [`docs/MVP_STATUS.md`](docs/MVP_STATUS.md) | MVP completion tracker |
| [`docs/SKILL_BUILDER.md`](docs/SKILL_BUILDER.md) | Skill architecture & dev guide |
| [`docs/`](docs/) | Product design · Database · API design |

---

<br/>

<p align="center">
  <sub>Made with 🔬 by researchers, for researchers</sub><br/>
  <sub>© 2024–2026 Chenxxxxxx06 · <a href="LICENSE">All Rights Reserved</a></sub>
</p>
