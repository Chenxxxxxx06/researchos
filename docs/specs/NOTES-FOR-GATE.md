# NOTES-FOR-GATE

Append-only notes from partition implementers for the gate/consolidator fixer.

## frontend-research (partition: frontend-research) — FINAL (completes the interrupted prior run)

All owned files were implemented against the REAL shipped backend
(`researchos/research/router.py` + `schemas.py` + `providers/*`) and the ALREADY-LANDED
`lib/api/{papers,ideas,research}.ts`, not the spec's draft §API. Deltas absorbed on my
side. **`tsc --noEmit` is clean for every file I own** (0 errors). The whole partition
uses semantic tokens only (verified: 0 `neutral-*/amber-*/emerald-*/red-*/white` hits)
and every user-visible string routes through `t()`.

### Whole-repo tsc status: GREEN as of this run

At one point during my build, `lib/i18n/dictionaries/en-US.ts` was missing 124 keys that
existed in zh-CN (namespaces `paper.*/anchorDialog.*/figureDialog.*/agg.*/prefs.*/run.*/
chart.*` — **zero `research.*`**), which was the single repo tsc error. A concurrent
partition has since landed those en-US counterparts: the two dictionaries are now in
**full key parity** and `corepack pnpm exec tsc --noEmit` reports **0 errors across the
whole repo**. Nothing outstanding on the i18n seam for my slice. (If that en-US work is
un-committed and gets reverted, re-add the en-US counterparts for those non-research
namespaces — owner: frontend-paper / experiments-figures.)

### CP-2 — `lib/api/agents.ts` (owner: frontend-ide) — LANDED, no action needed

The shipped `agents.ts` already provides everything CP-2 asked for, so I consumed it
directly:
- `AgentRunContext = { idea_id?; paper_id?; section_seqs?: number[] }` and
  `createAgentRun(..., { context })` — used for section/paper/idea seeds.
- `listAgentRuns(projectId, { limit?, offset? })` appends query params — so **chat
  "Load earlier" IS implemented** (not cut; the prior run's note is superseded).
- `AgentType` has **no `'ideate'`** and must stay that way — `/ideas/generate` is
  SYNCHRONOUS (returns `{ideas, gaps_considered, papers_used}`), per CONSOLIDATION §7.

### CP-3 — `lib/websocket/**` (owner: frontend-ide) — generic hook still absent (degraded as designed)

`useProjectAgentEvents` returns `{runs, trackRun}` but `LiveRun` has **no `agentType`
and no `prompt`**, and there is **no generic `useProjectEvents(projectId, onEvent)`
hook**. Documented degradations applied (all spec-sanctioned; nothing here blocks the
build):
- **Ingestion-status convergence = polling only.** `refetchInterval` on `['papers']`
  (in `PaperLibrary`, always mounted) and on `['paper-sections']` (in `ReadingRoom`)
  returns `4000` only while some item is `pending`/`running`, else `false`. No
  `paper.ingest.*` / `research.feed.updated` WS consumer is wired (would need a second
  socket — avoided the #54 leak).
- **Chat live-run filtering by tracked id.** `ResearchChat` renders live bubbles only
  for `runId ∈ pendingPrompts` (runs it launched), so critic runs (tracked by
  `IdeaCard`) that share the one socket never bleed into the chat column (AC #12).
  Optional later enhancement: if frontend-ide adds `LiveRun.agentType`, OR-in
  `run.agentType === 'research'`.
- `ResearchWorkspace` mounts exactly **one** `useProjectAgentEvents(projectId)` and fans
  `runs`/`trackRun` to `ResearchChat` + `IdeaPanel` as props.

### CP-4 — i18n dictionaries — already landed, NOT modified by me

The `research.*` keys (128) were already present and in lockstep in BOTH dicts before
this run; I added **no** new keys and touched neither dictionary. I reuse two existing
design-system keys where semantics fit (`common.save`, `common.cancel` in the feed
editor). `t()` already does `{name}` interpolation, so the spec's planned `interp()`
helper was unnecessary and NOT added.

### Route pages (single sanctioned overlap per CONSOLIDATION §9)

- `research/page.tsx` → thin `<ResearchWorkspace projectId/>` wrapper.
- NEW `research/read/[paperId]/page.tsx` → thin `<ReadingRoom projectId paperId/>` wrapper.

### Deleted (superseded old root files — moved into subfolders, retokenized)

`features/research/{PaperSearchPanel,IdeaPanel,ResearchChat,AgentRunMessage,CriticReviewCard}.tsx`
(the old `AgentRunMessage` used the OLD `CitationChip` `citation` prop and the old
`PaperSearchPanel` called the 3-arg `searchPapers` — both were the pre-existing type
errors; now gone). Logic moved to `chat/`, `ideas/`, `search/`.

### Cuts (SHOULD/STRETCH, per spec degradation rules)

- **Gap-matrix heat view** — CUT (CONSOLIDATION §7 binding: no `/ideas/gap-matrix`
  endpoint; list view only). `IdeaPanel` has no list/matrix toggle, no `GapMatrixView`.
- **Per-request `sources` search filter** — control hidden (CONSOLIDATION §7: not
  implemented server-side; provenance still shown from `extra.sources`).
- **`ChatSeed` kind `'gap'`** is retained in the store/banner/request mapping for
  forward-compat, but nothing seeds it now (it was only produced by the cut gap-matrix).

### Implemented beyond the MUST bar (SHOULD delivered)

Load-earlier chat pagination; `reingestPaper` retry button (reading room `failed`
branch); feed client-side dismiss (localStorage) + import via refs-based `importPapers`;
library client-side title filter (>15 papers); outline `IntersectionObserver` active
highlight; section "Show more" expander; feed score bar (reads `extra.score` when
present).
