<!--
  ╔══════════════════════════════════════════════════════════════╗
  ║                    R E S E A R C H O S                      ║
  ║          AI-Native Research Operating System                ║
  ╚══════════════════════════════════════════════════════════════╝
-->

<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=36&duration=3000&pause=1000&color=6366F1&center=true&vCenter=true&random=false&width=600&lines=ResearchOS;AI+Research+Operating+System;Experiment+%E2%86%92+Paper+%E2%86%92+Code;One+Workspace%2C+End+to+End" alt="ResearchOS" />

<img src="docs/assets/researchos-otter.png" width="240" alt="Rho, the ResearchOS research otter, connecting papers and code" />

<p>
  <sub><b>Meet Rho, the Research Otter.</b> Curious, tool-using, and serious about connecting every claim to its evidence.</sub>
</p>

<p>
  <a href="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml"><img src="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml/badge.svg?label=CI" alt="CI" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Proprietary-6366F1?style=flat" alt="Proprietary License" /></a>
  <a href="docs/TODO_ZH.md"><img src="https://img.shields.io/badge/maintenance-active-61E6B2?style=flat" alt="Actively maintained" /></a>
  <a href="#"><img src="https://img.shields.io/badge/python-3.13+-blue?logo=python&logoColor=white&color=3776AB" alt="Python" /></a>
  <a href="#"><img src="https://img.shields.io/badge/node-22+-green?logo=node.js&logoColor=white&color=339933" alt="Node" /></a>
  <a href="#"><img src="https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white" alt="PostgreSQL" /></a>
  <a href="#"><img src="https://img.shields.io/badge/tests-quality%20gated-blue?logo=pytest&logoColor=white" alt="Tests" /></a>
  <a href="mailto:3653448612@qq.com"><img src="https://img.shields.io/badge/ideas-welcome-brightgreen" alt="Ideas welcome" /></a>
</p>

<blockquote>
  <b>🔬 Research</b> · <b>💻 Code</b> · <b>🧪 Experiment</b> · <b>📝 Write</b><br/>
  One workspace, end-to-end AI-assisted research — from idea to paper
</blockquote>

<p>
  <sub>Built with ❤️ using <b>FastAPI</b> + <b>Next.js</b> + <b>PostgreSQL/pgvector</b> + <b>Redis</b> + <b>Docker</b></sub>
</p>

<p>
  <sub>ResearchOS is actively maintained. The current alpha favors verifiable progress, explicit limitations, and a durable research loop over inflated feature claims.</sub>
</p>

<p>
  <a href="README_zh.md">中文文档</a>
</p>

</div>

---

> See the [Chinese product and engineering blueprint](docs/PRODUCT_BLUEPRINT_ZH.md),
> [agent protocol](docs/AGENT_PROTOCOL_ZH.md), and [capability TODO](docs/TODO_ZH.md)
> for the unified research pipeline and execution boundaries.

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

### Terminal harness (alpha)

```bash
cd apps/api
uv pip install -e .

researchos init
researchos register --email you@example.com --display-name "Your Name"
researchos login --email you@example.com
researchos projects
researchos projects create --name "My Research"
researchos use <project-id>
researchos ask "Find the innovation and experiment gaps"
researchos chat
```

The CLI uses the real ResearchOS API and includes project selection, agent runs,
interactive sessions, provenance-aware memory, context manifests, and a local
Mission approval scaffold. See the
[CLI and scientific memory design](docs/HARNESS_CLI_MEMORY_ZH.md).

<p align="right">
  <sub><a href="#-manual-setup">Don't have pnpm? Click here →</a></sub>
</p>

---

## 🎯 Core Workspaces

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
| `pnpm test` | Backend pytest suite |
| `pnpm check` | Full quality gate: test + typecheck + build |
| `pnpm smoke:api` | API smoke test (16 endpoints) |
| `pnpm smoke:e2e` | Playwright E2E for core workspaces |

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
| 💻 Terminal panel | Real argv execution in `local` environments only; explicit development/read-only Git allowlist, cwd guard, timeout, and output cap; forcibly disabled in staging/production |
| 🌐 SSH runtime | Interface + permission model only (no remote connection) |
| 🎙️ Audio | Transcript analysis works; object storage, ASR, diarization, and timestamps are not implemented yet |

---

## 🗺️ Capability roadmap

The roadmap is maintained by honest capability state rather than release phases. See
[docs/TODO_ZH.md](docs/TODO_ZH.md) for acceptance criteria and safety boundaries.

| Capability | State |
|---|---|
| Zotero center, LLM connection test, innovation extraction | ✅ usable skeleton |
| Ownership tree and coordinator/worker agent protocol | ✅ usable skeleton |
| Research Inbox direction/meeting/transcript-to-paper flows | ✅ / 🟡 |
| Restricted real terminal, experiment progress/dataflow | ✅ usable skeleton |
| Live CCFDDL deadlines, simulated reviewer, release studio | ✅ usable skeleton |
| PDF annotation, experiment DAG, tagging, multimodal parsing, citation graph, venue formatting, rerun diff | ⚪ backlog |
| SSH/HPC/Slurm, isolated arbitrary commands, continuous Research Mission | ⚪ backlog |
| `researchos` / `ros` CLI, scientific context, Mission scaffold | ✅ usable skeleton |
| Claude / Codex / OpenClaw / nanobot execution adapters | ⚪ backlog; discovery and links only |
| GitHub Pages site and gated tag-release workflow | ✅ site deployed; release gate ready |

Have an idea for the next capability? Email
[3653448612@qq.com](mailto:3653448612@qq.com) with the use case, inputs, expected outputs, and acceptance criteria.

## 🙏 Design references

[academic-research-skills](https://github.com/Imbad0202/academic-research-skills) ·
[superpowers](https://github.com/obra/superpowers) ·
[Dify](https://github.com/langgenius/dify) ·
[agent-skills](https://github.com/addyosmani/agent-skills) ·
[nature-skills](https://github.com/Yuan1z0825/nature-skills) ·
[CCFA-Skills](https://github.com/mikubaka88/CCFA-Skills) ·
[ccf-deadlines](https://github.com/ccfddl/ccf-deadlines) ·
[CS Paper Review](https://cspaper.org/) ·
[LabVLA](https://zjunlp.github.io/LabVLA/) ·
[DiffBIR](https://0x3f3f3f3fun.github.io/projects/diffbir/)

Harness references:
[Claude Code](https://code.claude.com/docs/en/how-claude-code-works) ·
[OpenAI Codex](https://github.com/openai/codex) ·
[OpenClaw](https://github.com/openclaw/openclaw) ·
[nanobot](https://github.com/HKUDS/nanobot).
ResearchOS links to these projects and borrows architectural ideas; it does not
claim their implementations as ResearchOS code.

Design documents:
[Harness, CLI, and scientific memory](docs/HARNESS_CLI_MEMORY_ZH.md) ·
[Research education harness roadmap](docs/RESEARCH_EDUCATION_HARNESS_ROADMAP_ZH.md) ·
[promotion copy kit](docs/PROMOTION_COPY_ZH.md) ·
[GitHub Pages site](https://chenxxxxxx06.github.io/researchos/).

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

# Full backend test suite
pytest -q

# Specific modules
pytest -q tests/test_coding_chat.py tests/test_git_service.py tests/test_patches.py

# Full quality gate
pnpm check
```

---

## 📊 CI / Quality

<p align="center">
  <a href="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml"><img src="https://github.com/Chenxxxxxx06/researchos/actions/workflows/ci.yml/badge.svg?label=CI%20Status" alt="CI" /></a>
</p>

GitHub Actions (`.github/workflows/ci.yml`) · runs on push / PR:

| 🧪 Stage | ⚙️ Command | 🟢 Status |
|---|---|---|
| Backend Lint | `ruff check .` + `mypy researchos` | ✅ |
| Backend Test | `pytest -q` (PostgreSQL + Redis) | ✅ |
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

## 🔒 Ownership and contributions

ResearchOS is a proprietary project owned by **Chenxxxxxx06**. Source access does
not grant permission to copy, redistribute, commercialize, sublicense, or host
the project. Contributions require prior authorization and a separate written
contribution agreement. See [LICENSE](LICENSE) and [NOTICE.md](NOTICE.md).

<p align="center">
  <img src="https://raw.githubusercontent.com/andreasbm/readme/master/assets/lines/rainbow.png" alt="rainbow" />
</p>

<p align="center">
  <sub>Made with 🔬 by researchers, for researchers</sub><br/>
  <sub>© 2024–2026 Chenxxxxxx06 · <a href="LICENSE">All Rights Reserved</a></sub>
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
