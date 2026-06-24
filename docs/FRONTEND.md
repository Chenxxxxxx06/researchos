# ResearchOS Frontend Design

## 1. Stack

- Next.js with App Router
- TypeScript
- TailwindCSS
- Shadcn UI primitives
- Monaco Editor
- TanStack Query for server state
- Zustand or similar for local workspace state
- Recharts or ECharts for experiment visualization
- WebSocket client with typed event contracts

## 2. Application Structure

```text
apps/web/
  app/
    (auth)/
    (workspace)/
      projects/[projectId]/
        overview/
        research/
        ide/
        experiments/
        paper/
        skills/
        settings/
  components/
  features/
    research/
    ide/
    experiments/
    paper/
    skills/
    agents/
    runtime/
  lib/
    api/
    websocket/
    auth/
    permissions/
    editor/
```

## 3. Primary Navigation

- Project Overview
- Research Copilot
- AI IDE
- Experiments
- Paper Workspace
- Skills
- Settings

Each module should share the same project switcher, context status, agent activity tray, and notification/event feed.

## 4. Research Copilot UI

Layout:

- Left: project context, paper library filters, saved ideas.
- Center: conversational research thread with cited answers and tool traces.
- Right: source panel with papers, code repositories, datasets, baselines, and generated critique cards.

Expected controls:

- Search papers
- Summarize paper
- Generate related work
- Run novelty check
- Run critic review
- Save idea
- Convert to experiment plan

## 5. AI IDE UI

Layout:

- Left: file explorer and Git panel.
- Center: Monaco editor with tabs.
- Bottom: terminal/log panel.
- Right: AI coding assistant with selected files, proposed diffs, and task history.

Important states:

- Read-only remote file snapshot
- Unsaved local change
- Agent proposed patch
- Command running
- SSH disconnected
- Permission required before write or remote execution

## 6. Experiment Dashboard UI

Views:

- Runs table
- Run detail
- Live logs
- Metrics charts
- Artifact browser
- Comparison view
- Generated table/figure/caption candidates

Charts should support smoothing, multiple runs, selectable metrics, and export to paper assets.

## 7. Paper Workspace UI

Layout:

- Left: AI writing assistant and paper outline.
- Center: Monaco LaTeX editor with multi-file tabs.
- Right: PDF preview and compile log drawer.

Key interactions:

- Insert citation
- Rewrite selected text
- Generate section draft
- Fix compile error
- Insert result table
- Insert figure reference
- Generate reviewer response

## 8. Skills UI

Views:

- Marketplace catalog
- Installed skills
- Skill detail
- Permissions
- Version history
- Project enablement

Skill cards must show purpose, author, version, permissions, supported agents, required tools, and compatibility.

## 9. Real-Time UX

Use a unified activity model for:

- Agent token streaming
- Agent tool calls
- Experiment logs
- Metrics updates
- LaTeX compile progress
- Remote runtime status
- Skill installation

The UI should make long-running work visible, cancellable, and resumable.

## 10. Design Principles

- Dense but calm research workspace, not a marketing landing page.
- All generated text should show citations, source files, runs, or explicit assumptions.
- Agent actions that modify files, launch jobs, spend money, or use credentials require clear approval.
- The product should feel professional for daily research, with compact navigation and predictable panes.
