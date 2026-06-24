# ResearchOS Product Design

## 1. Product Positioning

ResearchOS is an AI-native research operating system for AI researchers, PhD students, independent researchers, ML engineers, and research labs. It unifies research discovery, agent-assisted reasoning, code work, remote experiments, paper writing, and reusable research skills in one SaaS platform.

It should feel like a combined workspace for:

- Perplexity-style research discovery
- Cursor-style AI IDE workflows
- Overleaf-style LaTeX authoring
- Weights & Biases-style experiment tracking
- Notion-style project knowledge organization
- App-store-style research skill distribution

The product is not a chatbot. The core product promise is: turn fragmented research work into a traceable, reproducible, AI-assisted workflow from idea to paper.

## 2. Target Users

### AI Research Student / PhD

- Needs fast paper discovery, related work organization, experiment tracking, LaTeX writing, and reviewer-style feedback.
- Values reproducibility, citation management, baseline comparison, and writing quality.

### Independent Researcher

- Needs an integrated workspace without institutional tooling.
- Values guided research planning, remote compute, reusable workflows, and paper templates.

### ML Engineer

- Needs experiment orchestration, remote GPU execution, logs, metrics, artifact tracking, and code assistance.
- Values operational reliability and integration with Git, Docker, and existing training scripts.

### Research Lab / Team

- Needs multi-user projects, shared memory, project knowledge graphs, permissions, templates, and auditability.
- Values collaboration, shared experiment history, and reusable lab-level skills.

## 3. Core Use Cases

- Generate and refine research ideas from project context and recent literature.
- Search papers, code, datasets, baselines, and technical trends.
- Run novelty and weakness analysis before committing to an idea.
- Convert ideas into implementation tasks, experiments, and paper outlines.
- Develop code in an AI IDE with project-aware agent assistance.
- Launch training jobs on remote GPU servers and monitor logs/metrics.
- Compare experiments and automatically generate tables, figures, captions, and result summaries.
- Write LaTeX papers with AI assistance, citations, BibTeX, live PDF preview, and reviewer response support.
- Download and run domain-specific skills, such as CVPR reviewer, Nature writing, VLM evaluation, or dataset curator.

## 4. Core Value

- One research graph: ideas, papers, code, experiments, results, figures, and final papers stay connected.
- One agent fabric: specialized agents collaborate across research, coding, experiments, writing, and critique.
- One execution layer: local and remote compute are managed through tracked tasks, logs, metrics, and artifacts.
- One extensibility model: skills package prompts, workflows, tools, memory schemas, and agent logic.
- One production-grade SaaS foundation: multi-tenant auth, billing-ready ownership, project permissions, observability, and secure runtime boundaries.

## 5. Product Moats

- Research Memory Graph that compounds project context over time.
- Experiment-to-paper synchronization that turns completed experiments into paper-ready assets.
- Skills Marketplace with third-party research workflows, templates, benchmarks, and reviewer personas.
- Agent orchestration specialized for research lifecycle tasks rather than generic chat.
- Deep integrations across literature, code, compute, experiment tracking, and LaTeX.

## 6. Product Modules

### Research Copilot

Paper search, project-aware Q&A, related work synthesis, novelty analysis, critic feedback, dataset/baseline recommendations, and future-work generation.

### AI IDE Workspace

Monaco-based editor, file tree, terminal, Git integration, multi-file agent edits, debugging assistance, SSH runtime integration, and remote training launch.

### Experiment Dashboard

Runs, jobs, logs, GPU metrics, loss/accuracy curves, artifact tracking, experiment comparison, result analysis, and paper asset generation.

### AI Paper Workspace

Three-pane workspace with assistant, LaTeX editor, and PDF preview. Supports citations, BibTeX, compile errors, academic rewriting, section generation, and reviewer response.

### Skills Marketplace

Discovery, installation, versioning, sandboxing, execution, and publishing of research skills, agents, workflows, prompts, templates, and benchmarks.

## 7. Product Principles

- Trace every AI action to source context, tool calls, and project artifacts.
- Keep researchers in control; agents propose, explain, and execute with permission boundaries.
- Prefer reproducibility over speed when experiments or papers are involved.
- Design for teams and labs from the beginning, even if the MVP launches for individual users.
- Separate product modules cleanly while sharing a common project, memory, event, and permission model.
