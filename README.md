<!--
  ╔══════════════════════════════════════════════════════════════╗
  ║                    R E S E A R C H O S                      ║
  ║          AI-Native Research Operating System                ║
  ╚══════════════════════════════════════════════════════════════╝
-->

<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=36&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&random=false&width=600&lines=ResearchOS;AI+Research+Operating+System;Experiment+%E2%86%92+Paper+%E2%86%92+Code;One+Workspace%2C+End+to+End" alt="ResearchOS" />

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
  <b>🔬 Research</b> · <b>💻 Code</b> · <b>🧪 Experiment</b> · <b>📝 Write</b><br/>
  One workspace, end-to-end AI-assisted research — from idea to paper
</blockquote>

<p>
  <sub>Built with ❤️ using <b>FastAPI</b> + <b>Next.js</b> + <b>PostgreSQL/pgvector</b> + <b>Redis</b> + <b>Docker</b></sub>
</p>

<p>
  <a href="README_zh.md">中文文档</a>
</p>

</div>

---

<p align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="rainbow" />
</p>

## 🚀 30-Second Quick Start

```bash
# One command to launch everything
pnpm stack:full

# Open your browser
open http://localhost:3000
```

| 🔑 Demo Account | |
|---|---|
| Email | `demo@researchos.dev` |
| Password | `demo-password-123` |

<p align="right">
  <sub><a href="#-manual-setup">Don't have pnpm? Click here →</a></sub>
</p>

---

## 🎯 Six Core Modules

<table>
<tr>
<td align="center" width="16%">
  <h3>🔍</h3>
  <b>Research Copilot</b>
</td>
<td width="50%">
  arXiv paper search · Personal library · Idea incubation · LLM chat · Peer review
</td>
<td width="34%">
  <sub>arXiv API · pgvector semantic search · Mock/Real LLM</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>🧠</h3>
  <b>AI IDE Workspace</b>
</td>
<td>
  File tree · Monaco editor · Coding Agent · Reviewable patches
</td>
<td>
  <sub>Monaco Editor · Git version control · Agent-driven patches</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>🧪</h3>
  <b>Experiment Dashboard</b>
</td>
<td>
  Experiment management · Run tracking · Recharts metrics · Logs · AI analysis
</td>
<td>
  <sub>Recharts visualization · Time-series metrics · Side-by-side comparison</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>📄</h3>
  <b>Paper Workspace</b>
</td>
<td>
  Three-panel LaTeX editor · AI writing assistant · Live preview
</td>
<td>
  <sub>LaTeX editing · AI-assisted writing · Compile & preview</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>🧩</h3>
  <b>Skills Marketplace</b>
</td>
<td>
  5 official Skills · One-click install & enable · Skill Builder for custom tools
</td>
<td>
  <sub>Plugin architecture · Hot-reload · Custom Skills</sub>
</td>
</tr>

<tr>
<td align="center">
  <h3>⚙️</h3>
  <b>Settings</b>
</td>
<td>
  Chinese/English toggle · Per-project LLM config · OpenAI / Anthropic
</td>
<td>
  <sub>i18n · Multi-model config · Project isolation</sub>
</td>
</tr>
</table>

---

## 🏗️ Architecture

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
│                     🗄️  Data Layer                       │
│       PostgreSQL (pgvector)  ·  Redis  ·  Docker        │
└─────────────────────────────────────────────────────────┘
```

---

## ⚡ Commands

| 🎯 Command | 📝 Description |
|---|---|
| `pnpm stack:full` | Full reset: down → up → migrate → seed |
| `pnpm stack:up` | Start all services |
| `pnpm stack:down` | Stop all services |
| `pnpm test` | Backend pytest (361 tests) |
| `pnpm check` | Full quality gate: test + typecheck + build |
| `pnpm smoke:api` | API smoke test (16 endpoints) |
| `pnpm smoke:e2e` | Playwright E2E (10 pages) |

```bash
# Windows users — also available via PowerShell
.\scripts\dev.ps1 full
.\scripts\dev.ps1 test
```

---

## 🚧 Current Mock/Stub Status

| 🔧 Feature | 📌 Status |
|---|---|
| 🤖 LLM (no API key) | Mock provider (deterministic, zero-cost). Settings → LLM → configure real key for Anthropic / OpenAI |
| 📜 LaTeX compilation | Mock text transform (no shell, no PDF). Real sandboxed latexmk compilation planned |
| 💻 Terminal panel | UI shell only (no command execution) |
| 🌐 SSH runtime | Interface + permission model only (no remote connection) |
| 🧩 Skill runtime injection | Skills installable & enabled. Agent runtime not yet injecting Skill prompt/workflow |

---

## 🗺️ Roadmap

> 💡 *Got an idea? [Open a Discussion](https://github.com/NPUwho/researchos/discussions) or send a PR!*

### 🔥 Phase 1 — Production Ready (v0.2)

| 🎯 Feature | 📌 Status |
|---|---|
| 🤖 Real LLM providers (Anthropic Claude · OpenAI GPT · DeepSeek) | 🟡 planned |
| 📜 Real LaTeX compilation (isolated latexmk in Docker) | 🟡 planned |
| 🌿 Git branch visualization & merge conflict resolution | 🟡 planned |
| 📊 Experiment metric comparison (side-by-side runs) | 🟡 planned |
| 🔐 OAuth2 / SSO login (Google, GitHub, ORCID) | 🟡 planned |
| 📎 File upload & attachment in chat | 🟡 planned |
| 🔔 Real-time notifications (WebSocket push) | 🟡 planned |
| 🌓 Dark mode auto-switch | 🟡 planned |

### 🚀 Phase 2 — Collaboration (v0.3)

| 🎯 Feature | 📌 Status |
|---|---|
| 👥 Multi-user real-time collaboration (Y.js CRDT) | ⚪ backlog |
| 💻 Real terminal with sandboxed execution (Firecracker/gVisor) | ⚪ backlog |
| 🌐 SSH runtime — connect to HPC / cloud GPU / Slurm | ⚪ backlog |
| 📚 Citation manager integration (Zotero · Mendeley · Paperpile) | ⚪ backlog |
| 📑 PDF annotation & inline highlighting | ⚪ backlog |
| 🧪 Automated experiment pipelines (DAG workflow) | ⚪ backlog |
| 📋 Research project templates (CS, Bio, Physics, etc.) | ⚪ backlog |
| 🏷️ Auto-tagging & smart categorization of papers | ⚪ backlog |

### 🌌 Phase 3 — Intelligence (v1.0)

| 🎯 Feature | 📌 Status |
|---|---|
| 🖼️ Multi-modal agent (images, plots, tables, equations) | ⚪ backlog |
| 🔗 Auto literature graph & citation network visualization | ⚪ backlog |
| 📝 Venue-specific paper auto-formatting (NeurIPS · ICML · ACL · Nature) | ⚪ backlog |
| ✅ Research reproducibility checker (rerun + diff outputs) | ⚪ backlog |
| 🧩 Community Skill Marketplace (publish & share skills) | ⚪ backlog |
| 📈 Research impact dashboard (citations, altmetrics, downloads) | ⚪ backlog |
| 🎙️ Voice-to-paper dictation & meeting summarization | ⚪ backlog |
| 🌍 Federated search across arXiv · Semantic Scholar · PubMed · OpenAlex | ⚪ backlog |
| 🧠 Active learning experiment suggestion | ⚪ backlog |
| 📦 One-click paper-to-code reproducibility bundle | ⚪ backlog |

### 🧪 Experimental / Maybe

| 🎯 Idea | 💭 Why |
|---|---|
| 🎮 Gamified peer review (review battles, reputation scores) | Make reviewing fun & incentivized |
| 🔮 Research direction predictor (trend forecasting from arxiv) | Spot hot topics early |
| 🧬 Protocol.io / Protocols.io integration | Reproducible wet-lab protocols |
| 📊 Live conference dashboard (acceptance rates, keyword trends) | Conference season tool |
| 🤝 "Lab-mate matching" — find collaborators by research interest | Build your research network |
| 🪄 "Explain this paper to a 5-year-old" — layered summarization | Science communication |
| 🔐 Blockchain timestamping for research claims | Priority & provenance |
| 📱 Mobile app — check experiments & approve patches on the go | True anywhere access |
| 🎨 Paper illustration generator (DALL·E / Stable Diffusion integration) | Auto-generate figures |
| 🌐 Self-hosted arXiv overlay (browse & annotate without leaving the app) | All-in-one workflow |

---

## 👩‍💻 Development

### 🛠️ Requirements

<p>
  <img src="https://img.shields.io/badge/Python-3.13+-3776AB?logo=python&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/Node.js-22+-339933?logo=node.js&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/pnpm-9.15+-F69220?logo=pnpm&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/PostgreSQL-16+%2Bpgvector-4169E1?logo=postgresql&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/Redis-7+-DC382D?logo=redis&logoColor=white&style=flat-square" />
  <img src="https://img.shields.io/badge/Git-required-F05032?logo=git&logoColor=white&style=flat-square" />
</p>

- conda environment `researchos` (conda-forge channel)
- corepack enabled: `corepack enable`

### 🧪 Running Tests

```bash
cd apps/api

# All 361 tests
pytest -q

# Specific modules
pytest -q tests/test_coding_chat.py tests/test_git_service.py tests/test_patches.py

# Full quality gate
pnpm check
```

---

## 📊 CI / Quality

<p align="center">
  <a href="https://github.com/NPUwho/researchos/actions/workflows/ci.yml"><img src="https://github.com/NPUwho/researchos/actions/workflows/ci.yml/badge.svg?label=CI%20Status" alt="CI" /></a>
</p>

GitHub Actions (`.github/workflows/ci.yml`) · runs on push / PR:

| 🧪 Stage | ⚙️ Command | 🟢 Status |
|---|---|---|
| Backend Lint | `ruff check .` + `mypy researchos` | ✅ |
| Backend Test | `pytest -q` (PostgreSQL + Redis, 361 tests) | ✅ |
| Frontend Typecheck | `pnpm -r typecheck` | ✅ |
| Frontend Build | `pnpm --filter web build` | ✅ |

<details>
<summary>💡 Git identity in CI</summary>

Test-commit git identity is injected via `GIT_AUTHOR_*` / `GIT_COMMITTER_*` env vars (configured in `researchos/git/runner.py`). CI does not need `~/.gitconfig`.
</details>

---

## 📚 Documentation

| 📖 Doc | 📝 Description |
|---|---|
| [`docs/RUNBOOK.md`](docs/RUNBOOK.md) | Ops guide & troubleshooting |
| [`docs/MVP_STATUS.md`](docs/MVP_STATUS.md) | MVP completion tracker |
| [`docs/SKILL_BUILDER.md`](docs/SKILL_BUILDER.md) | Skill architecture & dev guide |
| [`docs/`](docs/) | Product design · Database · API design |

---

## 🤝 Contributing

We welcome all contributions! Open an issue, send a PR, or share ideas in Discussions.

<p align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="rainbow" />
</p>

<p align="center">
  <sub>Made with 🔬 by researchers, for researchers</sub><br/>
  <sub>© 2024–2026 ResearchOS · <a href="LICENSE">MIT License</a></sub>
</p>

---

<details>
<summary><b>📦 Manual Setup</b> (use when pnpm is unavailable)</summary>

```bash
# Start with Docker
docker compose -f infra/docker/docker-compose.yml up -d --build
docker compose -f infra/docker/docker-compose.yml exec -T api alembic upgrade head
docker compose -f infra/docker/docker-compose.yml exec -T api python -m researchos.seed.demo
```

```powershell
# Windows PowerShell
.\scripts\dev.ps1 full
```
</details>
