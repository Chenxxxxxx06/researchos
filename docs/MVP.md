# ResearchOS MVP

## 1. MVP Goal

The MVP should prove the smallest complete research loop:

Idea or paper question -> literature context -> critique -> coding task -> experiment run -> tracked result -> paper-ready summary.

The first release should avoid building every surface at full depth. It should build one coherent project workspace with enough AI, data, and runtime infrastructure to validate that ResearchOS can become the user's daily research home.

## 2. Phase 1 Must-Have Scope

### Product Surfaces

- Project dashboard with recent papers, ideas, tasks, experiments, and paper drafts.
- Research Copilot chat with project context, paper search, paper summary, and novelty/critic responses.
- Basic AI IDE workspace with file tree, Monaco editor, terminal panel, and Git status read-only view.
- Experiment dashboard with run list, run detail, logs, metrics charts, artifacts, and comparisons.
- Paper workspace with LaTeX editor, compile action, PDF preview, and AI writing panel.
- Skills page with first-party bundled skills and install/enable/disable states.

### Backend Capabilities

- Multi-tenant auth, organizations, users, projects, and project membership.
- PostgreSQL domain schema for projects, papers, ideas, experiments, documents, agents, and skills.
- Redis for queues, streaming state, WebSocket fanout, rate limits, and short-lived task state.
- Celery workers for paper ingestion, RAG indexing, LaTeX compilation, remote command execution, and AI jobs.
- WebSocket gateway for chat streaming, task events, logs, metrics, and compile status.

### AI Capabilities

- Planner Agent for decomposing user goals into research actions.
- Research Agent with arXiv/Semantic Scholar style source connectors.
- Critic Agent for novelty, baseline, weakness, dataset, and reproducibility review.
- Latex Agent for writing, editing, citation insertion, and compile-error diagnosis.
- Experiment Agent for explaining metrics and suggesting next runs.
- Basic skill runtime that loads first-party skill manifests from the database or filesystem.

### Runtime Capabilities

- Local sandboxed command runner for MVP development tasks.
- SSH connection profiles, encrypted credentials, and remote command execution.
- Training job launcher that streams logs and basic metrics.
- LaTeX compile worker using isolated containers.

## 3. Deferred Features

- Full collaborative editing with CRDTs.
- Public third-party marketplace with payments and moderation.
- Browser-based full VSCode compatibility.
- Automatic large-scale benchmark orchestration.
- Fine-grained plugin SDK for arbitrary third-party tools.
- Team billing, procurement flows, and enterprise SSO.
- Full graph database migration; MVP can model graph edges in PostgreSQL.
- Automatic figure layout generation beyond simple chart/table assets.

## 4. High-Risk Features

- Secure arbitrary remote code execution and credential handling.
- Trust boundaries for third-party skills and tool calling.
- Reliable LaTeX compilation at scale with untrusted projects.
- Agent edit safety in real repositories.
- Accurate novelty detection and literature coverage.
- Real-time multi-user editing and conflict resolution.
- Experiment-to-paper sync without generating misleading claims.

## 5. MVP Closed Loop

1. User creates a project and adds a research topic.
2. Research Copilot searches papers and builds a project paper library.
3. Critic Agent generates novelty risks, missing baselines, datasets, and experiment suggestions.
4. User opens IDE workspace and asks Coding Agent to scaffold or modify experiment code.
5. User launches a remote training job.
6. Experiment dashboard tracks logs, metrics, artifacts, and completion status.
7. Experiment Agent summarizes results and generates candidate table/figure/caption data.
8. Paper workspace inserts result summary into LaTeX with citations and references.
9. Research Memory Graph links idea, papers, code commits, experiment runs, artifacts, and paper sections.

## 6. MVP Acceptance Criteria

- A user can complete the closed loop above in one project without leaving ResearchOS.
- All generated content is traceable to sources, runs, files, or explicit user instructions.
- All long-running jobs emit status events and can be retried or cancelled.
- Remote execution and LaTeX compilation run in isolated workers.
- The system stores enough structured data to support future collaboration, marketplace, and graph expansion.

## 7. Non-Goals for MVP

- Do not build a generic chat app.
- Do not build a toy demo with mocked experiments only.
- Do not require perfect autonomous research execution.
- Do not allow unreviewed third-party code execution.
- Do not optimize for marketplace supply before first-party workflows are strong.
