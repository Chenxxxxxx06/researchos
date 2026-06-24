# ResearchOS Roadmap

## Phase 1: Research Loop MVP

### Objective

Ship a single-user or small-team workspace that proves the research loop from paper discovery to experiment summary to paper draft.

### Major Deliverables

- Project dashboard
- Research Copilot with paper search, summaries, and critic feedback
- Basic IDE workspace
- Remote job launch and log streaming
- Experiment dashboard
- LaTeX editor and PDF compile preview
- First-party skills runtime
- Research Memory Graph v1 using PostgreSQL edges

### Success Metrics

- Users create projects and return to them repeatedly.
- At least one experiment run is linked to at least one paper section.
- Users accept or edit AI-generated related work, critique, or result summaries.
- Remote logs and metrics stream reliably.

## Phase 2: Collaboration and Reliability

### Objective

Turn the MVP into a reliable SaaS workspace for labs and teams.

### Major Deliverables

- Organization/team permissions
- Shared project memory and audit logs
- Git integration with branch awareness and PR summaries
- Improved SSH profiles, server pools, and job lifecycle controls
- More robust experiment comparison and artifact lineage
- Document versioning for LaTeX projects
- Agent run replay and observability

### Success Metrics

- Multiple users collaborate in one project.
- Experiment artifacts and paper outputs remain traceable across versions.
- Agent failures can be debugged from stored run traces.

## Phase 3: Skills Marketplace and Plugin Runtime

### Objective

Make ResearchOS extensible through skills, agents, workflows, templates, and benchmarks.

### Major Deliverables

- Skill package format and signing
- First-party marketplace
- Third-party submission review flow
- Skill sandboxing and permission prompts
- Plugin runtime for external APIs and tool adapters
- Skill analytics, ratings, compatibility, and version pinning

### Success Metrics

- Users install and use skills in real projects.
- Skills can be versioned, rolled back, and permissioned.
- Third-party skills cannot access unauthorized project data or tools.

## Phase 4: Research App Store and Advanced Automation

### Objective

Support richer research apps, lab-scale automation, and advanced memory/agent systems.

### Major Deliverables

- Research apps with UI extensions
- Advanced multi-agent planning and background monitors
- Experiment-to-paper sync with review gates
- Benchmark orchestration across remote GPU pools
- Knowledge graph visualization and graph-native queries
- Enterprise SSO, billing, compliance, and private marketplaces

### Success Metrics

- Labs adopt ResearchOS as their primary research operations platform.
- Research apps and skills become reusable assets across projects.
- Automated workflows save measurable time without weakening reproducibility.

## Roadmap Guardrails

- Security boundaries must advance before marketplace openness.
- Traceability must remain visible in all AI-generated paper content.
- Remote execution must stay isolated and observable.
- Skills must be useful as first-party workflows before third-party scale.
