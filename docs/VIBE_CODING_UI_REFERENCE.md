# Vibe Coding UI Reference Study

Reviewed against public product pages on 2026-08-19:

- Bolt: https://bolt.new
- v0: https://v0.app
- Cursor: https://cursor.com
- Replit: https://replit.com (public page blocked by its security service in this environment)
- Windsurf: https://windsurf.com (rate-limited and redirected in this environment)

## Patterns worth adopting

### Prompt as the primary action

Bolt and v0 make one large, low-friction composer the first meaningful control. Supporting actions stay inside or immediately below the composer. ResearchOS adopts this as the project-level Mission Composer, where a research question can create a real persisted Mission.

### Work grouped by state

Cursor presents work as in-progress and ready-for-review queues rather than a flat list of tools. ResearchOS keeps this principle in Mission Control through task state, approval gates, artifacts, events, and a selected-task inspector.

### One dominant work surface

The strongest products reserve most space for the active editor, preview, or generated result. Secondary context remains narrow and collapsible. ResearchOS applies this to Research, IDE, Experiments, and Paper workspaces.

### Restrained controls

v0 and Cursor use short labels, neutral surfaces, one strong action color, compact icon buttons, and obvious focus states. ResearchOS retains its evidence green as the single product accent and uses semantic colors only for real state.

### Immediate feedback

Good Vibe Coding interfaces acknowledge actions with pressed states, local loading placeholders, live task status, review gates, and reversible changes. ResearchOS applies:

- 150ms button and tab transitions
- hover lift on primary and secondary actions
- pressed feedback
- animated local skeletons
- panel and popover entry motion
- persistent Agent and Runtime state
- no decorative scroll animation

## Patterns intentionally rejected

- marketing-page blue glow as the product workspace background
- hidden autonomous execution without task state
- fake progress or invented metrics
- permanent three-panel layouts at small laptop widths
- automatic approval of code, compute, credentials, or release
- motion that does not communicate state or feedback

ResearchOS is not a website generator. It borrows interaction clarity from Vibe Coding products while preserving evidence provenance and human approval as core product behavior.
