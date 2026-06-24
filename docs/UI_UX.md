# ResearchOS UI/UX Design

## 1. UX Positioning

ResearchOS should feel like a professional research cockpit: dense, reliable, and calm. It should prioritize scanning, traceability, and repeat workflows over decorative presentation.

## 2. Global Layout

- Top bar: organization, project switcher, search, active agent status, user menu.
- Left rail: Overview, Research, IDE, Experiments, Paper, Skills, Settings.
- Main area: module-specific workspace.
- Right tray: contextual agent activity, source details, or inspector.

## 3. Project Overview

Purpose: show the state of the research project at a glance.

Sections:

- Active research goals
- Recent papers
- Open ideas
- Running experiments
- Paper draft status
- Installed skills
- Recent agent activity

## 4. Research Copilot Experience

The user should be able to ask questions, search papers, save sources, generate related work, and run critique without losing context.

Important UX details:

- Every cited answer shows source chips.
- Tool calls are visible but compact.
- Novelty and critic outputs use structured cards.
- Ideas can be saved and converted into tasks or experiments.

## 5. IDE Experience

The IDE should support serious code work without trying to fully clone desktop VSCode in MVP.

Core panes:

- File tree
- Editor tabs
- Terminal/logs
- AI assistant
- Diff review

Risky actions, such as file writes and remote execution, need approval states that are easy to inspect.

## 6. Experiment Experience

The experiment dashboard should make status and comparison effortless.

Core views:

- Runs table with status, owner, metric summary, commit, and duration.
- Run detail with logs, metrics, config, artifacts, and agent summary.
- Compare view with metric overlays and config differences.
- Paper assets view for generated tables, figures, and captions.

## 7. Paper Workspace Experience

The paper workspace uses a three-pane layout:

- Left: AI assistant, outline, citations.
- Center: LaTeX editor.
- Right: PDF preview and compile logs.

Key UX principle: AI edits should remain inspectable and reversible.

## 8. Skills Experience

Skills should feel like installable research capabilities, not prompt snippets.

Skill detail should show:

- What it does
- Supported agents
- Required permissions
- Example workflows
- Version history
- Compatibility
- Author and trust level

## 9. Traceability UX

AI-generated outputs should visually link to:

- Source papers
- Code files
- Experiment runs
- Artifacts
- User-provided assumptions
- Agent run trace

This is critical for research trust.

## 10. Empty States

Empty states should offer direct actions:

- Create project
- Search papers
- Import PDF
- Create idea
- Connect runtime
- Create experiment
- Start paper draft
- Install first-party skill

Avoid marketing copy inside the product workspace.
