# ResearchOS Skills System

## 1. Definition

A ResearchOS Skill is a packaged research capability. It is more than a prompt.

Skills include:

- Prompt instructions
- Workflow graph
- Tool permissions
- Memory schema
- Agent logic bindings
- Domain knowledge
- UI/action metadata
- Compatibility constraints

## 2. Skill Package

```text
skill/
  skill.yaml
  prompts/
  workflows/
  knowledge/
  schemas/
  examples/
  templates/
  tests/
```

## 3. Manifest Example

```yaml
id: cvpr-reviewer
name: CVPR Reviewer Skill
version: 1.0.0
author: researchos
description: Simulates CVPR-style reviewer critique.
agents:
  - critic
  - research
permissions:
  tools:
    - paper.search
    - memory.read
    - experiment.read
  memory:
    read:
      - papers
      - experiments
      - paper_sections
    write:
      - critiques
compatibility:
  min_platform_version: 0.1.0
runtime:
  sandbox: restricted
```

## 4. Skill Lifecycle

1. Published to marketplace or bundled as first-party.
2. Validated by package scanner.
3. Installed at organization or project level.
4. Enabled for selected projects.
5. Injected into compatible agent runs.
6. Emits usage telemetry and audit logs.
7. Updated, pinned, rolled back, or disabled.

## 5. Runtime Model

Skills never execute privileged operations directly. A skill can request capabilities, and the platform runtime decides whether the active user, project, and policy allow them.

Runtime responsibilities:

- Load manifest and assets.
- Validate version and compatibility.
- Build skill context for an agent.
- Enforce tool permissions.
- Enforce memory permissions.
- Log skill usage.
- Block unsafe package behavior.

## 6. Dynamic Loading

MVP:

- First-party skills stored as records and filesystem packages.
- Runtime loads prompt fragments, workflow definitions, and permission declarations.
- No arbitrary third-party code execution.

Later:

- Signed skill bundles.
- Isolated plugin workers.
- Compatibility testing.
- Marketplace review pipeline.
- Revocation and vulnerability advisories.

## 7. Skill Types

- Writing skill: venue style, paper templates, reviewer response.
- Reviewer skill: venue-specific critique, novelty, weakness, reproducibility.
- Evaluation skill: benchmark workflows, metric templates, result interpretation.
- Coding skill: framework-specific code generation and debugging.
- Dataset skill: dataset discovery, formatting, licensing checks.
- Figure skill: chart style, captions, export formatting.
- Workflow skill: multi-agent plan for a full research task.

## 8. Marketplace Requirements

- Search and filters by domain, venue, task, agent, rating, and permissions.
- Skill detail with manifest, examples, changelog, permissions, and compatibility.
- Install, enable, disable, pin version, and rollback.
- Admin review for third-party submissions.
- Abuse reporting and revocation.
- Private organization marketplace for labs.

## 9. Security Model

Skills are treated as untrusted until proven otherwise.

Controls:

- Permission declarations
- User approval prompts
- Static package validation
- Signed bundles
- Sandboxed execution
- Network egress controls
- Tool-call auditing
- Secrets redaction
- Version pinning

## 10. First-Party MVP Skills

- General Research Copilot
- Novelty Critic
- CVPR Reviewer
- Related Work Builder
- LaTeX Academic Writer
- Experiment Result Analyst
- VLM Evaluation Planner
- Baseline Recommender
