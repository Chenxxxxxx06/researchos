# Spec: frontend-research — Research Discovery & Reading UX

Workstream: `frontend-research` · Realizes INNOVATION_IDEAS WS1-1/WS1-2 (frontend), WS1-3 (frontend surface), WS1-5 phase 1, WS1-6 (frontend), WS5-1 (frontend), plus ARCHITECTURE_MAP frontend issues #53, #57 and the research-side of #54/#59.

Owned partition:
- `apps/web/features/research/**`
- `apps/web/lib/api/research.ts` (exists today), plus new `apps/web/lib/api/papers.ts` and `apps/web/lib/api/ideas.ts`

Everything else (app routes, `lib/api/agents.ts`, `lib/websocket/**`, i18n dictionaries, shared-schemas, backend) is consumed via **Cross-partition requests** (§10).

---

## Objective (user-visible outcome, tied to owner wishlist)

1. **Wishlist 1 (find papers):** The Discover rail becomes a real fielded search console — category multi-select, date range, author/title fields, relevance/latest sort, source badges (arXiv / S2 / OpenAlex) with a merged-provenance tooltip, citation counts, "load more" pagination, and one-click import that shows a live ingestion-status chip (full text fetched / abstract only / failed). A new **Feed tab** ("Latest in my areas") surfaces fresh papers in followed categories with import/dismiss.
2. **Wishlist 2 (analyze/explain papers):** Library papers open an in-app **Reading Room**: sectioned full text (from the new paper-sections API), a sticky clickable outline, and a per-section **"Explain this"** action that drops the user into the research chat pre-seeded with that section's context. Agent answers carry **citation-integrity chips** that resolve keys to real library papers (or flag them unverified).
3. **Wishlist 3 (idea generation):** The Ideas panel gains **"Generate ideas from library"** (IDEATE agent), rendering results as a list of gap-typed idea cards with cited-support links into the Reading Room (MUST), a gap-matrix heat view (SHOULD), and a **"Develop this idea"** handoff that pre-seeds the research chat.
4. **Chat polish:** live prompt bubble (no more "Processing…"), streaming + tool-call chips retained, reconnect-safe via the hardened WS client (owned by frontend-ide), library-aware suggestion chips, "load earlier" history.

All new/rewritten components use the semantic design tokens (frontend-shell WS7-1) and ship zh-CN + en-US keys (full list in §12).

---

## Current state (concrete, file:line)

**Search** — `apps/web/features/research/PaperSearchPanel.tsx`
- :14-17 — mutation posts only `{query, limit:10}` via `searchPapers(projectId, query, 10)`; no filters, no offset.
- :36 — hardcoded English placeholder `"Search arXiv…"`; the whole file has zero i18n.
- :42-46 — "Import all" bulk-imports the entire result array; no per-result dedup indicator.
- :50-57 — result card shows `source:external_id` as a mono span; no source badge, no citation count, no provenance, no "already in library" state, no pagination ("no results" is the only terminal state).
- Backend counterpart `apps/api/researchos/research/router.py:36-42` passes only `query`/`limit`; `PaperSearchFilters` is dead plumbing (ARCHITECTURE_MAP §3.2), arXiv provider ignores filters (`providers/arxiv.py:76-95`).

**Library** — `apps/web/features/research/PaperLibrary.tsx`
- :27 — each paper is an `<a target="_blank">` straight to arxiv.org; no in-app detail view, no delete, no ingestion status (the `Paper` model has no sections today).
- :23 — passive empty state `"No papers yet."`.

**Chat** — `apps/web/features/research/ResearchChat.tsx`
- :22-23 — `hasRealLLM = configs.length > 0` heuristic (ARCHITECTURE_MAP #59), duplicated across the app.
- :25-28 — history fetches only the first page and `.reverse()`s it, depending on undocumented newest-first order (#53).
- :44 — `liveOnly` includes **every** live run in the project (critic runs launched from the Ideas panel stream into the chat column).
- :83 — persisted bubble falls back to `` `(${run.status})` ``; :88-90 — citations render as raw `arxiv:2401.12345` mono spans, no resolution, no links.
- `AgentRunMessage.tsx:12` — the live user bubble shows `'Processing…' / 'Done'` because `LiveRun` doesn't carry the prompt (#53).
- No seeding mechanism: nothing can open the chat with paper/section/idea context; `createAgentRun` context is typed `{ idea_id?: string }` only (`lib/api/agents.ts:47`).

**Ideas** — `apps/web/features/research/IdeaPanel.tsx`
- :19-28 — critic completion detected by critique-**count-growth** polling at 1.5s (`refetchInterval: reviewing ? 1500`), with a `baselineCount` ref; server failure → "Reviewing…" forever (#57).
- No generation path at all — ideas are hand-typed titles (`create.mutate` :30-33); `Idea.novelty_score` is never displayed; no supporting-paper links.

**API client** — `apps/web/lib/api/research.ts`
- :67-76 — `searchPapers(projectId, query, limit)`; :78-83 — `importPapers` posts client-held `PaperResult[]` wholesale; :85-87 — `listPapers` unpaginated call; `Paper` (:16-30) has no `ingestion_status`; `PaperResult` (:3-14) has no `doi`/`citation_count`/provenance.

**Events** — `packages/shared-schemas/src/events.ts:11-62` has no `paper.*` or feed family; `useProjectAgentEvents.ts` (`apps/web/lib/websocket/`) has no reconnect/no seq dedup (#54, being fixed by frontend-ide) and `LiveRun` (:14-21) lacks `agent_type` and the user prompt.

**i18n** — `lib/i18n/dictionaries/zh-CN.ts` has `nav.research` but zero `research.*` keys; the entire research surface is untranslated English.

**Route** — `apps/web/app/(workspace)/projects/[projectId]/research/page.tsx:10-22` composes the four panels directly; there is no reading-room route.

---

## Design (algorithms & data flow)

### D1. Component topology & the thin-route pattern

The app-route file is reduced to a 6-line wrapper (cross-partition request CP-1) around a single owned export, so all future reorganization stays inside the partition:

```
app/(workspace)/projects/[projectId]/research/page.tsx        → <ResearchWorkspace projectId/>
app/(workspace)/projects/[projectId]/research/read/[paperId]/page.tsx → <ReadingRoom projectId paperId/>   (new route, CP-1)
```

`features/research/ResearchWorkspace.tsx` layout (3 columns, same geometry as today's page):

```
┌ left rail (w-64) ──┐ ┌ center ─────────────┐ ┌ right rail (w-80) ────┐
│ PaperLibrary       │ │ ResearchChat        │ │ Tabs: Discover | Feed │
│ ──────────────     │ │  (chat/…)           │ │  SearchPanel          │
│ IdeaPanel (v2)     │ │                     │ │  FeedTab              │
└────────────────────┘ └─────────────────────┘ └───────────────────────┘
```

- Right-rail tab state is local `useState<'discover'|'feed'>`, initialized from `?focus=feed|search` (read via `useSearchParams`) so the onboarding checklist (WS7-4) and feed WS toasts can deep-link.
- `ResearchWorkspace` mounts exactly **one** `useProjectAgentEvents(projectId)` and one generic `useProjectEvents(projectId, handler)` (CP-3) and passes the results down as props — fixing the one-socket-per-component leak on this page (#54's frontend-research share).
- The generic handler routes: `paper.ingest.*` → patch the `['papers', projectId]` cache in place (see D3) and invalidate `['paper-sections', projectId, paper_id]`; `research.feed.updated` → invalidate `['feed', projectId]`.

### D2. Search panel v2 (fielded query builder + federation display + pagination)

Data flow, numbered:

1. **State**: `SearchPanel` holds `query: string`, `filters: SearchFilters` (see §API), and `pages: PaperResult[][]` (accumulated result pages), `offset`, `hasMore`, `providerErrors`.
2. **Query builder** (`QueryBuilder.tsx`): a collapsible section under the query input (collapsed by default; a filter-count badge like "Filters · 3" when any filter is active). Controls:
   - **Categories**: `CategoryPicker` — checkbox popover fed by the static `arxivTaxonomy.ts` (curated ~45 categories grouped `cs.*`, `stat.*`, `math.*`, `eess.*`, `physics/astro/quant-ph`; each `{id:'cs.LG', label:'Machine Learning'}`). Selected categories render as removable chips. No network dependency — taxonomy is a checked-in constant.
   - **Date range**: two native `<input type="date">` (from/to), either optional.
   - **Author**, **Title**: plain text inputs (compiled server-side to `au:`/`ti:` — WS1-1 step 2).
   - **Sort**: segmented control `relevance | latest`.
   - **Sources**: three toggle chips `arXiv / Semantic Scholar / OpenAlex`, all on by default; maps to `filters.sources`.
3. **Submit** → `searchPapers(projectId, { query, limit: 20, offset: 0, filters })`; response replaces `pages`, sets `hasMore`/`providerErrors`. **Load more** → same call with `offset += 20`, appended as a new page. Changing query/filters resets pagination. Client-side dedup guard: skip results whose `source:external_id` already appeared in `pages` (defensive vs provider offset drift).
4. **Result card** (`SearchResultCard.tsx`): title (links `url`, external), authors line (first 3 + "+N"), abstract 2-line clamp, then a badge row:
   - `SourceBadge` per entry of `result.provenance` (deduped by source). Colors: arXiv `danger`-tinted, S2 `accent`-tinted, OpenAlex `success`-tinted (token colors, not hardcoded Tailwind hues). Hovering the badge group opens a **provenance tooltip** — a positioned popover (pure CSS `group-hover` + `focus-within`, no dependency) listing each `{source, external_id, url}` row and, when present, `doi` and `citation_count` ("Cited by 132 · OpenAlex").
   - `citation_count` chip when non-null.
5. **Import**: if `result.in_library` → static "In library ✓" chip that links to the reading room (`/research/read/{paper_id}` — `in_library_paper_id` from the API). Else "+ Library" button → `importPapers(projectId, [result])` → on success: patch the card to imported state, invalidate `['papers', projectId]`, and render an `IngestionStatusChip` bound to the returned paper (see D3). "Import all" is **removed** (deliberate UX supersession: bulk-echo import hid dedup/ingestion feedback; per-item import with visible status replaces it — see §11 rationale).
6. **Errors**: per-provider partial failure is not fatal — `provider_errors` renders as a dismissible warn-token notice line ("Semantic Scholar unavailable — showing arXiv + OpenAlex results"). Whole-request failure renders error + retry. `429` (`ApiError.status === 429`) renders the rate-limit message.

### D3. Ingestion-status chip (import → sections lifecycle)

1. Backend import now enqueues full-text ingestion (backend-research WS1-3); `Paper` gains `ingestion_status: 'pending' | 'full_text' | 'abstract_only' | 'failed'`.
2. `IngestionStatusChip({status})` renders: `pending` → pulsing dot + "Fetching full text…" (warn tokens); `full_text` → "Full text ✓" (success tokens); `abstract_only` → "Abstract only" (muted); `failed` → "Fetch failed" (danger, tooltip advises retry from reading room).
3. **Live update path**: `ResearchWorkspace`'s generic WS handler receives `paper.ingest.completed {paper_id, ingestion_status, section_count}` and does `queryClient.setQueryData(['papers', projectId], patch item)` — no refetch storm.
4. **Fallback path (MUST work without WS)**: the `['papers']` query sets `refetchInterval: (q) => q.state.data?.items.some(p => p.ingestion_status === 'pending') ? 4000 : false`. This keeps the chip converging even if the generic hook (CP-3) ships late or the socket is down; interval self-disables when nothing is pending.

### D4. "Latest in my areas" Feed tab

1. `FeedTab` queries `listFeed(projectId, { status: 'new', limit: 20, offset })` (accumulating "load more" like search).
2. Header row: title, count pill, **Refresh** button → `refreshFeed(projectId)` (202; button shows spinner then invalidates after `research.feed.updated` or a 5s timer), and a gear button toggling the `FollowedCategoriesEditor`.
3. `FollowedCategoriesEditor`: fetches `getFeedSettings(projectId)` → `{followed_categories}`; renders the same `CategoryPicker` (reused component) + Save → `putFeedSettings`. Empty categories → editor shows hint "Follow categories to build your feed" and the tab's empty state deep-links here.
4. Feed item card = `SearchResultCard` variant with: relative published date, score bar (0–1 → 4-step width bar, accent tokens, title tooltip "Fit to your library"), Import (→ `importFeedItem`, then same ingestion-chip flow; on success item flips to imported state) and Dismiss (`dismissFeedItem`, optimistic removal, rollback on error).
5. Offline/degraded: feed endpoints returning empty pages (no daemon run yet, no network) render the actionable empty state — never an error wall.

### D5. Reading Room (paper detail + sectioned full text + explain handoff)

1. Route `/projects/{pid}/research/read/{paperId}` renders `ReadingRoom`. Queries: `getPaper(projectId, paperId)` and `getPaperSections(projectId, paperId)` (the latter with `refetchInterval` 4s while `ingestion_status === 'pending'`).
2. **Layout**: header (back link to `/research`, title, authors, venue · date, `IngestionStatusChip`, external links "arXiv ↗" / "PDF ↗", "Explain paper" button) over a two-column body: sticky outline (w-56, `position: sticky; top: 0`, own scroll) + section stream.
3. **Outline** (`SectionOutline`): one row per section, indented by `level`, `kind` glyph (intro/method/experiments/related/conclusion get distinct small markers). Click → `document.getElementById('sec-'+seq).scrollIntoView({behavior:'smooth'})` + `aria-current`. Active-section highlight via one `IntersectionObserver` over section headings (SHOULD; click-to-scroll alone is the MUST bar).
4. **Section stream** (`SectionCard` per section): heading row (`h2/h3` by level) with a hover-revealed **"Explain this"** button; body rendered as pre-wrapped paragraphs (split on blank lines; no markdown/LaTeX rendering in v1 — body is plain text from the extractor). Long bodies (> 4000 chars) get a "Show more" expander to keep the DOM light.
5. **States**: `ingestion_status='pending'` → skeleton sections + notice; `'abstract_only'` → single Abstract section from `paper.abstract` + muted explainer ("Full text unavailable — explanations will use the abstract"); `'failed'` → danger notice + **Retry ingestion** button (`retryIngestion`, SHOULD).
6. **Explain handoff**: "Explain this" → `useChatSeedStore.getState().setSeed({ kind:'section', projectId, paperId, paperTitle, citationKey, sectionSeq, sectionHeading })` then `router.push('/projects/{pid}/research')`. "Explain paper" seeds `{kind:'paper', …}` (no sectionSeq).

### D6. Chat seed store & pre-seeded runs

`features/research/chatSeed.ts` — a tiny zustand store (zustand is already a project dependency):

```ts
export type ChatSeed =
  | { kind: 'section'; paperId: string; paperTitle: string; citationKey: string; sectionSeq: number; sectionHeading: string }
  | { kind: 'paper';   paperId: string; paperTitle: string; citationKey: string }
  | { kind: 'idea';    ideaId: string; ideaTitle: string }
  | { kind: 'gap';     problem: string; method: string; paperKeys: string[] };
interface ChatSeedState { seed: ChatSeed | null; setSeed(s: ChatSeed): void; clear(): void; }
```

`ResearchChat` reads the store: when `seed` is non-null it renders a `ContextBanner` above the composer ("Explaining §3 Method of «Attention Is All You Need» · ✕") and pre-fills the input with a template ("Explain this section to me: what is the key idea and how does it work?" / "Help me develop this idea: …" — i18n'd). On send, the seed maps into the run request:

| seed.kind | `createAgentRun` body |
|---|---|
| section | `{ agent_type:'research', message, context:{ paper_id, section_seqs:[sectionSeq] } }` |
| paper   | `{ agent_type:'research', message, context:{ paper_id } }` |
| idea    | `{ agent_type:'research', message, context:{ idea_id } }` |
| gap     | `{ agent_type:'research', message: message + '\n\nGap context: method "{method}" has not been applied to problem "{problem}". Supporting papers: {keys}' }` (context-free; keys inline) |

Seed clears after a successful send or on ✕. Store is session-only (no persistence) — a navigation away and back keeps it until used, which is the desired "carry this to chat" semantic.

### D7. Chat polish (streaming, prompts, filtering, suggestions, pagination)

1. **Live prompt bubble**: `ResearchChat` keeps `pendingPrompts: Record<runId, {message: string; seed: ChatSeed | null}>` in state; `mutation.onSuccess` records `res.agent_run_id → {message, seed}` before `trackRun`. `AgentRunMessage` gains a `prompt?: string` prop rendered in the user bubble; falls back to a muted "(streaming run)" only for runs from other tabs. Fixes AgentRunMessage.tsx:12.
2. **Run filtering**: chat renders persisted runs where `agent_type === 'research'` plus live runs where `run.agentType === 'research'` (CP-3 adds `agentType` to `LiveRun`, populated from the `agent.run.started` payload) **or** `runId ∈ pendingPrompts` (covers the started-event-missed race). Critic/ideate runs no longer bleed into the chat column; ideate runs render in the Ideas panel (D8).
3. **Reconnect safety**: consumed, not built — the hardened client (frontend-ide) reconnects with backoff and replays missed **persisted** events via `GET /agents/runs/{id}/events?after_seq=`; `useProjectAgentEvents`'s external contract (`{runs, trackRun}`) is unchanged (CP-3 pins it). ResearchChat additionally invalidates `['agent-runs']` when any tracked run reaches a terminal status (already present at :35-38, kept) so token-loss during a disconnect self-heals from the persisted output.
4. **Citation-integrity chips** (`CitationChip` v2 + `citations.ts`):
   - `useCitationResolver(projectId)` builds `Map<'source:external_id', {paperId, title}>` from the `['papers']` query cache (`select` memoized).
   - Chip resolution ladder per citation: (a) key in library map → **verified-in-library** chip: success-token dot + truncated title, links to `/research/read/{paperId}`; (b) not in library but the run's completed payload carries `{title, url}` (live runs / `PaperCitation`) → **verified-external** chip: neutral, links `url`, tooltip "Cited from search — not in your library"; (c) key only (persisted `output_json.citations: string[]`) and unresolvable → **unverified** chip: muted + dashed border + tooltip "Could not verify this source against your library". This is the honest UI for the whitelist mechanism (ARCHITECTURE_MAP #26): the agent's citation keys become inspectable instead of decorative.
   - Applied to persisted bubbles, live bubbles, and `CriticReviewCard.citations_json`.
5. **Library-aware suggestions** (`SuggestionChips` + pure `suggestions.ts`): rendered in the empty state and under the composer when input is empty. `buildSuggestions(papers, ideas, t)` returns ≤ 3 deterministic entries: library empty → ["Search for papers on…" (focuses Discover tab), "What can this copilot do?"]; library non-empty → ["Summarize «{newest paper title}»" (seeds `{kind:'paper'}`), "What connects {title₁} and {title₂}?" (plain message), ideas exist → "Stress-test my idea «{title}»" (seeds `{kind:'idea'}`)]. Pure function, no LLM, mock-safe.
6. **Load earlier** (SHOULD): "Load earlier" button above the oldest message → `listAgentRuns(projectId, {limit: 20, offset})` accumulation (CP-2 adds the options param); rendering stays `reverse()`ed per page group.
7. **Mock badge**: keep the amber pill but i18n it and read the shared helper if frontend-shell ships one (`lib/llm/status` — soft dependency; otherwise keep the local `configs.length > 0` check in one place, `ResearchChat` only).

### D8. Idea panel v2 (generation, gap display, critic flow fix, develop handoff)

1. **Generate**: "Generate ideas from library" button → `generateIdeas(projectId)` → `{agent_run_id}`; `trackRun(agent_run_id)`; panel shows a progress row (streaming status from the shared `runs` map — tool chips reused). On terminal status: invalidate `['ideas']` and `['gap-matrix']`. Disabled with tooltip when library `total < 3` ("Import at least 3 papers first").
2. **Idea list (MUST)**: `IdeaCard` per idea — title, status pill, `gap_type` badge when present (`coverage`/`limitation`/`transfer` mapped to token-tinted labels), `novelty_score` as "Novelty 0.72" pill when non-null, expandable body: description, hypothesis, **supporting papers** as citation-integrity chips (same resolver — in-library ones deep-link to the Reading Room; that is the "per-idea cited-support links" requirement), critiques (existing `CriticReviewCard`, restyled to tokens), actions row: **Run critic**, **Develop this idea** (seeds `{kind:'idea'}` → chat), Archive (PATCH status, SHOULD).
3. **Critic flow fix** (#57): `review.mutate` returns `agent_run_id` → track it; completion = `runs[agent_run_id].status ∈ {completed, failed}` → invalidate `['critiques', ideaId]`, stop the spinner; `failed` renders the error inline. Keep a 5s `refetchInterval` **only while** a critic run is in flight as the no-WS fallback; delete the `baselineCount` count-growth heuristic entirely.
4. **Gap-matrix heat view (SHOULD)**: `GapMatrixView` behind a `list | matrix` segmented toggle. Data: `getGapMatrix(projectId)`. Render a CSS-grid: column heads = methods (rotated 45° labels, truncated), row heads = problems; cell background = 4-step accent alpha scale by `paper_keys.length` (0 = dashed-border "gap" cell). Cell click → popover: covering papers as chips (→ Reading Room) or, for gap cells, a **"Draft idea for this gap"** button seeding `{kind:'gap'}` into chat. Horizontal scroll container for wide matrices; `status:'empty'` → hint to run generation first. No chart library — pure grid.

### D9. Library panel v1.5

`PaperLibrary` rows become in-app links to `/research/read/{id}` (title + compact `IngestionStatusChip` dot variant + kebab: "Open original ↗", "Delete" → `deletePaper` with confirm). Actionable empty state: "No papers yet — search arXiv, S2 & OpenAlex →" button focusing the Discover tab. A client-side filter input appears when `total > 15` (filters the loaded page by title substring; server-side library search is out of scope).

### D10. Theming & states discipline

Every component in this partition uses semantic token classes only: `bg-bg`, `bg-surface`, `bg-surface2`, `border-border`, `text-text`, `text-muted`, `bg-accent text-accentFg`, and `success|warn|danger` tints for status chips (per frontend-shell WS7-1 token names). No `neutral-*`/`amber-*`/`emerald-*` literals in new code. If the token sweep has not landed when this partition builds, the classes compile to no-ops under Tailwind and the implementer applies the WS7-1 fallback mapping table as a temporary local constant — build never breaks either way. Every data surface implements the loading (Skeleton) / error (message + retry button) / empty (actionable CTA) triad.

---

## API contract changes

This partition ships no backend code; these are the **exact contracts the frontend is written against**. They are mirrored verbatim in Cross-partition request CP-5 for the backend-research partition; the consolidator must reconcile any drift before implementation starts.

### A1. `POST /projects/{project_id}/papers/search` — extended (backward compatible)

Request:
```json
{
  "query": "diffusion policy",
  "limit": 20,
  "offset": 0,
  "filters": {
    "categories": ["cs.LG", "cs.RO"],
    "date_from": "2026-01-01",
    "date_to": null,
    "author": "Chi",
    "title": null,
    "sort": "latest",
    "sources": ["arxiv", "s2", "openalex"]
  }
}
```
All of `offset`/`filters` optional; omitted ⇒ today's behavior. `sort ∈ {"relevance","latest"}`.

Response `200`:
```json
{
  "results": [
    {
      "source": "arxiv",
      "external_id": "2303.04137",
      "title": "Diffusion Policy: Visuomotor Policy Learning via Action Diffusion",
      "abstract": "…",
      "authors": ["Cheng Chi", "…"],
      "venue": "arXiv",
      "published_at": "2023-03-07T00:00:00Z",
      "url": "https://arxiv.org/abs/2303.04137",
      "pdf_url": "https://arxiv.org/pdf/2303.04137",
      "doi": "10.48550/arXiv.2303.04137",
      "citation_count": 812,
      "provenance": [
        {"source": "arxiv", "external_id": "2303.04137", "url": "https://arxiv.org/abs/2303.04137"},
        {"source": "openalex", "external_id": "W4323568234", "url": "https://openalex.org/W4323568234"}
      ],
      "in_library": false,
      "in_library_paper_id": null,
      "extra": {}
    }
  ],
  "limit": 20,
  "offset": 0,
  "has_more": true,
  "provider_errors": [{"source": "s2", "error": "timeout"}]
}
```
Errors: `429 rate_limited` (Retry-After honored as message only), `400 validation_error` (bad date range), partial provider failure is **not** an error (surfaces in `provider_errors`).

### A2. `POST /projects/{project_id}/papers/import` — response extended
Request unchanged (`{papers: PaperResult[]}` — client echoes results it received; if backend-research moves to reference-based import `{refs:[{source,external_id}]}`, only `papers.ts` changes — flagged in CP-5). Response papers gain `"ingestion_status": "pending"`.

### A3. `GET /projects/{project_id}/papers` / `GET …/papers/{paper_id}` — `PaperResponse` gains `ingestion_status` (existing rows backfilled `abstract_only`).

### A4. `GET /projects/{project_id}/papers/{paper_id}/sections` — **new**
```json
{
  "ingestion_status": "full_text",
  "sections": [
    {"seq": 0, "level": 1, "heading": "Introduction", "kind": "intro", "body": "…", "char_count": 4213}
  ]
}
```
`kind ∈ {abstract,intro,method,experiments,related,conclusion,appendix,other}`. `pending|failed|abstract_only` → `sections: []`. `404` unknown paper.

### A5. `POST /projects/{project_id}/papers/{paper_id}/reingest` — **new (SHOULD)** → `202 {"queued": true}`.

### A6. Feed — **new**
- `GET /projects/{project_id}/research/feed?status=new&limit=20&offset=0` → `Page<FeedItem>`; `FeedItem = {id, source, external_id, title, abstract, authors, url, pdf_url, published_at, score: number(0..1), status: 'new'|'imported'|'dismissed', created_at}`.
- `POST /projects/{project_id}/research/feed/{item_id}/import` → `201 PaperResponse` (with `ingestion_status`).
- `POST /projects/{project_id}/research/feed/{item_id}/dismiss` → `204`.
- `POST /projects/{project_id}/research/feed/refresh` → `202 {"queued": true}` (offline ⇒ still 202; a later `research.feed.updated {new_count: 0}` or nothing).
- `GET|PUT /projects/{project_id}/research/feed/settings` → `{"followed_categories": ["cs.LG","cs.CL"]}` (PUT body identical; `422` on non-taxonomy ids is NOT required — server accepts arbitrary strings, client only offers taxonomy).

### A7. Ideas — extended/new
- `IdeaResponse` gains `"gap_type": "coverage"|"limitation"|"transfer"|null` and `"supporting_paper_keys": ["arxiv:2303.04137"]` (default `[]`).
- `POST /projects/{project_id}/ideas/generate` → `201 {"agent_run_id","status","stream"}` (IDEATE agent run; `409 library_too_small` when < 3 papers).
- `GET /projects/{project_id}/ideas/gap-matrix` → `{"status":"ready","generated_at":"…","problems":["…"],"methods":["…"],"cells":[{"problem_idx":0,"method_idx":1,"paper_keys":["arxiv:…"]}]}` or `{"status":"empty"}`.

### A8. Agent runs (existing router, consumed) — `POST /projects/{id}/agents/runs` `context` accepts `{idea_id?, paper_id?, section_seqs?: int[]}`; `GET /projects/{id}/agents/runs` honors `limit/offset` (already paginated server-side per `Page[T]`).

---

## WS events

Consumed (producers = backend-research; envelope per `websocket/envelopes.py`):

| event_type | resource_type | payload |
|---|---|---|
| `paper.ingest.started` | `paper` | `{"paper_id": "…"}` |
| `paper.ingest.completed` | `paper` | `{"paper_id": "…", "ingestion_status": "full_text"\|"abstract_only", "section_count": 12}` |
| `paper.ingest.failed` | `paper` | `{"paper_id": "…", "error": "…"}` |
| `research.feed.updated` | `project` | `{"new_count": 7}` |

Existing `agent.run.*` family consumed unchanged. All four new events are optional enhancements at the UI layer — every consumer has a polling/refetch fallback (D3.4, D4.2, D8.3), so the frontend ships even if the event producers slip.

## DB changes

None (frontend-only workstream). All schema needs (`paper_sections`, `papers.ingestion_status`, `feed_items`, feed settings storage, `ideas.gap_type`/`support`) belong to backend-research and are restated in CP-5 for the consolidating migration agent.

## shared-schemas additions

For the consolidating agent (`packages/shared-schemas/src/events.ts`):
1. `PAPER_EVENTS = ['paper.ingest.started','paper.ingest.completed','paper.ingest.failed'] as const` and `RESEARCH_FEED_EVENTS = ['research.feed.updated'] as const`, folded into `EVENT_TYPES`.
2. `ResourceType` union gains `'paper'`.
3. Payload interfaces: `PaperIngestStartedPayload {paper_id: string}`, `PaperIngestCompletedPayload {paper_id: string; ingestion_status: 'full_text'|'abstract_only'; section_count: number}`, `PaperIngestFailedPayload {paper_id: string; error: string}`, `ResearchFeedUpdatedPayload {new_count: number}`; a `ResearchEventPayloadMap` mirroring `AgentEventPayloadMap`.
4. `AgentType` union (events.ts:94) gains `'ideate'` (and stays in sync with whatever coding/latex additions other specs make).

## New dependencies

None. Multi-select, tooltips, date inputs, the heat matrix, and the seed store are built from native elements + CSS + the already-present zustand/TanStack Query. (Deliberate: no `cmdk`, no headlessui, no chart lib.)

---

## File-by-file plan

All paths relative to `apps/web/`. (≈ est. lines; total ≈ 2,150.)

**lib/api**
| File | Action | Contents |
|---|---|---|
| `lib/api/papers.ts` | **create** (~170) | Types: `PaperResult` v2 (`doi`, `citation_count`, `provenance`, `in_library`, `in_library_paper_id`), `Paper` v2 (`ingestion_status`), `SearchFilters`, `SearchResponse`, `PaperSection`, `SectionsResponse`, `FeedItem`, `FeedSettings`, `IngestionStatus`. Fns: `searchPapers(projectId, req)`, `importPapers`, `listPapers(projectId, {limit,offset})`, `getPaper`, `deletePaper`, `getPaperSections`, `reingestPaper`, `listFeed`, `importFeedItem`, `dismissFeedItem`, `refreshFeed`, `getFeedSettings`, `putFeedSettings`. |
| `lib/api/ideas.ts` | **create** (~100) | `Idea` v2 (`gap_type`, `supporting_paper_keys`), `Critique`, `GapMatrix`; `listIdeas`, `createIdea`, `updateIdea`, `runCriticReview`, `listCritiques`, `generateIdeas`, `getGapMatrix`. |
| `lib/api/research.ts` | **modify** (~12) | Becomes a barrel: `export * from './papers'; export * from './ideas'; export type { Page } from './papers';` — keeps any out-of-partition import path stable. |

**features/research (root)**
| File | Action | Contents |
|---|---|---|
| `ResearchWorkspace.tsx` | **create** (~110) | D1 layout, right-rail tabs, `?focus=` handling, single `useProjectAgentEvents` + `useProjectEvents` mount, WS→cache routing, props fan-out. |
| `chatSeed.ts` | **create** (~40) | D6 zustand store + `ChatSeed` type. |
| `citations.ts` | **create** (~70) | `parseCitationKey`, `useCitationResolver(projectId)`, `resolveCitation(key, payloadCitations, libraryMap) → ChipModel` ladder (D7.4). Pure logic separated for future unit tests. |
| `CitationChip.tsx` | **rewrite** (~75) | Three-state chip (in-library link / external link / unverified), CSS tooltip, token styling. |
| `ToolCallChip.tsx` | **modify** (~20Δ) | Token colors (`warn/success/danger` tints), i18n'd status title attr. Keeps `LiveToolCall` prop shape. |
| `PaperLibrary.tsx` | **rewrite** (~110) | D9: reading-room links, dot ingestion chip, delete w/ confirm, client filter, actionable empty state, i18n, pending-ingest refetchInterval. |
| `PaperSearchPanel.tsx` | **delete** | Superseded by `search/SearchPanel.tsx`. |
| `IdeaPanel.tsx` | **delete** | Moved to `ideas/IdeaPanel.tsx`. |
| `ResearchChat.tsx` / `AgentRunMessage.tsx` | **delete** | Moved under `chat/`. |
| `CriticReviewCard.tsx` | **delete** | Moved to `ideas/CriticReviewCard.tsx`. |

**features/research/search**
| File | Action | Contents |
|---|---|---|
| `search/arxivTaxonomy.ts` | **create** (~85) | `ARXIV_CATEGORIES: {id, label, group}[]` (~45 curated entries), `groupCategories()` helper. |
| `search/SearchPanel.tsx` | **create** (~190) | D2 state machine: query, filters, page accumulation, dedup guard, provider-error notice, load-more, empty/loading/error triad, i18n. |
| `search/QueryBuilder.tsx` | **create** (~140) | Collapsible fielded controls, active-filter count badge, reset. |
| `search/CategoryPicker.tsx` | **create** (~95) | Checkbox popover over taxonomy groups + selected chips; reused by feed editor. Keyboard accessible (real `<button>`/`<input type=checkbox>`). |
| `search/SourceBadge.tsx` | **create** (~55) | Badge + grouped provenance tooltip (doi, citation_count rows). |
| `search/SearchResultCard.tsx` | **create** (~120) | D2.4/2.5 card; `variant: 'search'|'feed'` (score bar + dismiss in feed variant). |
| `search/IngestionStatusChip.tsx` | **create** (~50) | D3.2 chip, `variant: 'full'|'dot'`. |

**features/research/feed**
| File | Action | Contents |
|---|---|---|
| `feed/FeedTab.tsx` | **create** (~140) | D4 list, refresh, import/dismiss (optimistic), empty→editor CTA. |
| `feed/FollowedCategoriesEditor.tsx` | **create** (~85) | Settings fetch/save around `CategoryPicker`, dirty state, save/cancel. |

**features/research/reading**
| File | Action | Contents |
|---|---|---|
| `reading/ReadingRoom.tsx` | **create** (~160) | D5 page component (exported for the thin route), header, status branches, retry-ingest. |
| `reading/SectionOutline.tsx` | **create** (~70) | Sticky outline, kind glyphs, scroll-to, IntersectionObserver active highlight. |
| `reading/SectionCard.tsx` | **create** (~75) | Heading + explain button + clamped body + expander. |

**features/research/chat**
| File | Action | Contents |
|---|---|---|
| `chat/ResearchChat.tsx` | **rewrite/move** (~230) | D6/D7: seed banner + template prefill, `pendingPrompts`, research-only run filtering, citation chips on persisted bubbles, suggestions, load-earlier (SHOULD), mock badge, i18n. Receives `runs`/`trackRun` as props from `ResearchWorkspace`. |
| `chat/AgentRunMessage.tsx` | **rewrite/move** (~95) | `prompt` prop in user bubble, tool chips, streaming body, citation chips via resolver, error state. |
| `chat/ContextBanner.tsx` | **create** (~55) | Seed pill (kind icon + label + ✕), token styling. |
| `chat/SuggestionChips.tsx` | **create** (~55) | Chip row; click → prefill/seed/focus per suggestion action. |
| `chat/suggestions.ts` | **create** (~55) | Pure `buildSuggestions(papers, ideas, t)` (D7.5). |

**features/research/ideas**
| File | Action | Contents |
|---|---|---|
| `ideas/IdeaPanel.tsx` | **rewrite/move** (~190) | D8: generate button + streaming progress row, list of `IdeaCard`s, critic run tracking via `runs` prop (deletes count-polling), view toggle (list/matrix). |
| `ideas/IdeaCard.tsx` | **create** (~110) | Gap badge, novelty pill, support chips (resolver), critiques, Run critic / Develop / Archive. |
| `ideas/CriticReviewCard.tsx` | **move+modify** (~35Δ) | Token styling, i18n section titles, citation chips instead of raw keys. |
| `ideas/GapMatrixView.tsx` | **create** (~130, SHOULD) | D8.4 CSS-grid heat view + cell popover + gap→chat seeding. |

---

## Cross-partition requests

**CP-1 · App routes (owner: frontend-shell / routes):**
1. Replace `app/(workspace)/projects/[projectId]/research/page.tsx` body with the thin wrapper: `const { projectId } = use(params); return <ResearchWorkspace projectId={projectId} />;` importing `{ ResearchWorkspace } from '@/features/research/ResearchWorkspace'`.
2. Create `app/(workspace)/projects/[projectId]/research/read/[paperId]/page.tsx`: `'use client'; const { projectId, paperId } = use(params); return <ReadingRoom projectId={projectId} paperId={paperId} />;` importing `{ ReadingRoom } from '@/features/research/reading/ReadingRoom'`.

**CP-2 · `lib/api/agents.ts` (owner: frontend-ide):**
- Widen `AgentType` to include `'ideate'` (and others as needed).
- `createAgentRun` body type: `context?: { idea_id?: string; paper_id?: string; section_seqs?: number[] }`.
- `listAgentRuns(projectId: string, opts?: { limit?: number; offset?: number }): Promise<Page<AgentRun>>` (append query params).

**CP-3 · `lib/websocket/**` (owner: frontend-ide):** keep `useProjectAgentEvents(projectId): { runs: Record<string, LiveRun>; trackRun(runId: string): void }` stable; add to `LiveRun` the field `agentType?: string` (from `agent.run.started` payload) and (nice-to-have) `usage`. Export a generic subscription hook with exact signature `useProjectEvents(projectId: string, onEvent: (env: EventEnvelope) => void): void` (single shared socket, reconnect-safe). frontend-research degrades to documented polling fallbacks if `useProjectEvents` is cut.

**CP-4 · i18n dictionaries (owner: frontend-shell):** add the ~70 `research.*` keys listed in §12 to `lib/i18n/dictionaries/zh-CN.ts` and `en-US.ts` verbatim.

**CP-5 · Backend (owner: backend-research):** implement §API A1–A8 and §WS events exactly as specified; specifically (a) `PaperSearchRequest` gains `offset` + `filters` (categories/date_from/date_to/author/title/sort/sources) compiled per WS1-1, response gains `has_more`/`provider_errors`/result `doi|citation_count|provenance|in_library|in_library_paper_id`; (b) `PaperResponse.ingestion_status` + `GET /papers/{id}/sections` + optional `POST /papers/{id}/reingest`; (c) feed CRUD + settings + refresh per A6; (d) `IdeaResponse.gap_type` + `supporting_paper_keys`, `POST /ideas/generate` (IDEATE `AgentType`), `GET /ideas/gap-matrix`; (e) research agent honors `context.paper_id`/`section_seqs` by injecting those section bodies into the prompt; (f) **mock LLM provider extended deterministically** for: explain-with-section-context (echoes section heading in output + cites the paper key), IDEATE (returns 2 fixed gap-typed ideas citing library keys) — so the whole surface demos offline; (g) WS producers for `paper.ingest.*` / `research.feed.updated`. If backend-research prefers reference-based import (`{source, external_id}` list), notify: only `lib/api/papers.ts#importPapers` changes.

**CP-6 · e2e (owner: qa/test partition, or wherever `apps/web/e2e` lands):** add `apps/web/e2e/research.spec.ts` per §Test plan (content spec'd there; this partition cannot write into `e2e/`).

---

## MUST / SHOULD / STRETCH breakdown

**MUST**
- `papers.ts`/`ideas.ts`/`research.ts` barrel split; all types per §API.
- `ResearchWorkspace` shell + Discover/Feed tabs + single WS mount + thin-route handoff (CP-1).
- Search v2: query builder (categories, date range, author, sort, sources), source badges + provenance tooltip, citation-count chip, load-more pagination, per-result import with `IngestionStatusChip`, in-library state, provider-error notice. "Import all" removed.
- Ingestion chip with polling fallback (works without WS events).
- Feed tab: list, import, dismiss, refresh, followed-categories editor (functional, minimal styling).
- Reading Room: header, section stream, sticky outline (click-to-scroll), abstract-only/pending/failed branches, "Explain this" per section + "Explain paper" → chat seed handoff.
- Chat: seed store + `ContextBanner` + context-carrying `createAgentRun`, live prompt bubbles, research-only run filtering, citation-integrity chips (3-state) on live + persisted answers, suggestion chips, i18n, token styling.
- Ideas v2: generate button + streamed progress, gap-typed idea list with cited-support chips → Reading Room, "Develop this idea" handoff, critic completion via run status (count-polling deleted).
- All §12 i18n keys wired (CP-4); loading/error/empty triads everywhere.

**SHOULD**
- Gap-matrix heat view (`GapMatrixView`) with gap-cell → chat seeding.
- Outline active-section highlight (IntersectionObserver); section "Show more" expander.
- Chat "Load earlier" pagination (needs CP-2 `listAgentRuns` opts).
- `reingestPaper` retry button; feed optimistic dismiss rollback; library client-side filter; feed score-bar tooltip.
- Live WS handling of `paper.ingest.*` / `research.feed.updated` (on top of the polling fallback).

**STRETCH**
- One-click import of unverified citation chips (chip "+" action calling search-by-id then import).
- Compare-papers composer (multi-select library rows → seeded compare prompt).
- Feed "hide imported/dismissed" filter tabs and seen-state batching.

Degradation rules for the implementer: cut STRETCH silently; cut SHOULD by feature (each is isolated); if CP-3's generic hook is missing, ship with polling fallbacks only; if CP-5 lands partially, each panel's error/empty state must still render (404 on new endpoints → treat as empty with a "backend feature not yet available" muted note, keyed `research.common.notAvailable`).

---

## Acceptance criteria (each verifiable with local gates or by reading code/UI)

1. `pnpm tsc --noEmit` and `pnpm next build` pass in `apps/web` (tsc validates every new contract type and the CP-2/CP-3 consumed signatures).
2. `grep -r "Search arXiv" features/research` → 0 hits; `grep -rE "text-neutral-|bg-neutral-|amber-|emerald-" apps/web/features/research` → 0 hits (token discipline).
3. `features/research/**` contains no `import` from `app/` and `app/` route files import only `ResearchWorkspace`/`ReadingRoom` from this partition (code review of CP-1 wrappers).
4. `SearchPanel` submits `{query, limit, offset, filters}` and renders `provenance` badges + `provider_errors` notice — verify by reading `SearchPanel.tsx`/`SearchResultCard.tsx` against §A1.
5. `IngestionStatusChip` renders all four statuses and `['papers']` query's `refetchInterval` is a function returning `4000` only while some item is `pending` (read `PaperLibrary.tsx`).
6. No `setTimeout`-based or count-growth completion detection remains anywhere in the partition: `grep -n "baselineCount\|refetchInterval: reviewing" features/research` → 0 hits; critic/ideate completion reads run status from the shared `runs` map.
7. `chatSeed.ts` seed of kind `section` results in `createAgentRun` body containing `context: {paper_id, section_seqs:[n]}` (read `chat/ResearchChat.tsx` submit path).
8. `CitationChip` implements the 3-state ladder with in-library chips linking `/research/read/{paperId}` (read `citations.ts` + `CitationChip.tsx`).
9. Live chat bubbles render the user's actual prompt (`pendingPrompts` map wired into `AgentRunMessage`).
10. Every listed zh-CN key in §12 exists with an en-US counterpart and every new component calls `t()` for user-visible strings (spot-check grep `useI18n` across new files; no hardcoded sentence-case English strings in JSX).
11. Feed tab, Reading Room, Ideas panel each render a non-crashing actionable empty state when their endpoints return empty/404 (read the error branches).
12. `Object.values(runs)` consumers filter by `agentType`/tracked-id so critic runs never render in the chat column (read `ResearchChat.tsx`).

## Test plan (CI-run; local machine runs static gates only)

**Playwright (`apps/web/e2e/research.spec.ts` via CP-6; runs against the seeded demo stack + mock LLM, no external network — search tests stub the backend which itself uses recorded fixtures per backend-research):**
1. `research page renders three panes` — login as demo, open `/research`, assert Library/Chat/Discover visible, Feed tab switch works.
2. `fielded search and import` — open filters, pick `cs.LG`, set sort=latest, submit; assert a result card with a source badge; click "+ Library"; assert ingestion chip appears and library count increments.
3. `reading room + explain handoff` — open a seeded library paper (backend seed provides one `full_text` paper), assert outline items ≥ 3, click a section's "Explain this", assert redirect to `/research` with ContextBanner text containing the section heading; send; assert a streamed assistant bubble appears (mock provider deterministic) with ≥ 1 citation chip.
4. `ideas generate + develop` — click "Generate ideas from library" (seed guarantees ≥ 3 papers), await new idea cards with a gap badge (mock IDEATE deterministic), expand one, click "Develop this idea", assert chat ContextBanner shows the idea title.
5. `feed settings roundtrip` — open Feed → editor, follow `cs.LG`, save, assert chip persists after reload (GET/PUT settings).
6. `critic completion` — run critic on an idea; assert spinner resolves to a critique card without page reload.

**Pure-function tests (deferred CI, colocated `*.test.ts` compiled by tsc even before a unit runner exists in web):** `suggestions.test.ts` (empty/non-empty library matrices), `citations.test.ts` (resolution ladder incl. malformed keys) — written as plain exported assertion functions invoked by the Playwright spec's beforeAll (no new test framework dependency; upgrade to vitest is out of scope).

**Backend pytest coverage of A1–A8 belongs to backend-research** (their spec; CP-5 restates the contract so their contract tests and this client cannot drift).

## Explicitly out of scope

- Backend providers, ingestion pipeline, feed daemon, embeddings, IDEATE agent internals, mock-provider changes (backend-research owns; CP-5).
- PDF rendering / pdfjs viewer and select-text-in-PDF explain (WS1-5 phase-1 PDF pane) — the Reading Room is sections-first; the PDF stays an external link this session.
- Paper Tutor v2 (depth levels, quizzes, `[[sec:N]]` grounding walkthrough) — WS1-5 phase 2, needs real-LLM iteration.
- WS client hardening, reconnect, replay, `agents.ts` edits (frontend-ide; CP-2/CP-3).
- Design-token definitions, ThemeProvider, dictionaries files themselves (frontend-shell; CP-4).
- Server-side library search, novelty-gauntlet UI (WS5-2), similar-papers panel (WS1-4 §5), command-palette entries for research actions (frontend-shell registry can import our routes later).
- Alembic migrations and `packages/shared-schemas` file edits (consolidating agent; §DB/§shared-schemas list the needs).

---

## §12. i18n keys (add to both dictionaries via CP-4)

| Key | zh-CN | en-US |
|---|---|---|
| research.search.title | 发现论文 | Discover papers |
| research.search.placeholder | 搜索 arXiv、Semantic Scholar、OpenAlex… | Search arXiv, Semantic Scholar, OpenAlex… |
| research.search.filters | 筛选 | Filters |
| research.search.categories | 学科分类 | Categories |
| research.search.dateFrom | 起始日期 | From date |
| research.search.dateTo | 截止日期 | To date |
| research.search.author | 作者 | Author |
| research.search.fieldTitle | 标题包含 | Title contains |
| research.search.sort | 排序 | Sort |
| research.search.sortRelevance | 相关度 | Relevance |
| research.search.sortLatest | 最新 | Latest |
| research.search.sources | 数据源 | Sources |
| research.search.reset | 重置筛选 | Reset filters |
| research.search.search | 搜索 | Search |
| research.search.searching | 搜索中… | Searching… |
| research.search.loadMore | 加载更多 | Load more |
| research.search.noResults | 没有找到结果，试试放宽筛选条件。 | No results — try relaxing the filters. |
| research.search.import | + 加入文库 | + Library |
| research.search.imported | 已加入 | Imported |
| research.search.inLibrary | 已在文库 ✓ | In library ✓ |
| research.search.citedBy | 被引 {n} | Cited by {n} |
| research.search.providerError | {source} 暂不可用，已展示其余来源结果 | {source} unavailable — showing other sources |
| research.search.rateLimited | 搜索过于频繁，请稍后再试。 | Too many searches — try again shortly. |
| research.ingest.pending | 抓取全文中… | Fetching full text… |
| research.ingest.fullText | 已获取全文 | Full text ✓ |
| research.ingest.abstractOnly | 仅摘要 | Abstract only |
| research.ingest.failed | 全文抓取失败 | Full-text fetch failed |
| research.ingest.retry | 重试抓取 | Retry fetch |
| research.feed.title | 我的领域最新 | Latest in my areas |
| research.feed.refresh | 刷新 | Refresh |
| research.feed.dismiss | 忽略 | Dismiss |
| research.feed.editCategories | 关注的分类 | Followed categories |
| research.feed.categoriesHint | 关注分类后，这里会持续出现你领域的新论文。 | Follow categories to keep fresh papers from your areas flowing here. |
| research.feed.empty | 暂无新论文。关注一些分类，或点击刷新。 | No new papers yet. Follow some categories or hit refresh. |
| research.feed.fitScore | 与文库匹配度 | Fit to your library |
| research.library.title | 文库 | Library |
| research.library.empty | 文库还是空的 | Your library is empty |
| research.library.emptyCta | 去搜索论文 → | Search for papers → |
| research.library.open | 打开阅读 | Open reader |
| research.library.openOriginal | 查看原文 ↗ | Open original ↗ |
| research.library.delete | 从文库移除 | Remove from library |
| research.library.deleteConfirm | 确认从文库移除这篇论文？ | Remove this paper from the library? |
| research.library.filter | 筛选文库… | Filter library… |
| research.reading.back | 返回研究台 | Back to research |
| research.reading.outline | 大纲 | Outline |
| research.reading.explainSection | 解释此节 | Explain this |
| research.reading.explainPaper | 解读全文 | Explain paper |
| research.reading.abstract | 摘要 | Abstract |
| research.reading.pendingBody | 正在抓取并解析全文，稍等片刻… | Fetching and parsing the full text — hang tight… |
| research.reading.abstractOnlyNote | 暂无全文，解释将基于摘要。 | Full text unavailable — explanations will use the abstract. |
| research.reading.showMore | 展开全文 | Show more |
| research.reading.showLess | 收起 | Show less |
| research.chat.title | Research Copilot | Research Copilot |
| research.chat.placeholder | 询问论文、方法、数据集… | Ask about papers, methods, datasets… |
| research.chat.emptyTitle | 提出一个研究问题 | Ask a research question |
| research.chat.emptyBody | 例如：“视觉-语言预训练的最新方法有哪些？” | E.g. "What are the latest methods for vision-language pretraining?" |
| research.chat.mockBadge | Mock LLM — 请在设置中配置 API Key | Mock LLM — set an API key in Settings |
| research.chat.sources | 引用来源 | Sources |
| research.chat.unverified | 未能在文库中核实该来源 | Could not verify this source against your library |
| research.chat.externalSource | 来自搜索结果，尚未加入文库 | Cited from search — not in your library |
| research.chat.contextSection | 正在解释《{title}》§{heading} | Explaining §{heading} of "{title}" |
| research.chat.contextPaper | 正在解读《{title}》 | Explaining "{title}" |
| research.chat.contextIdea | 正在发展想法「{title}」 | Developing idea "{title}" |
| research.chat.contextGap | 空白点：{method} × {problem} | Gap: {method} × {problem} |
| research.chat.clearContext | 清除上下文 | Clear context |
| research.chat.loadEarlier | 加载更早的对话 | Load earlier |
| research.chat.streamingRun | （进行中的对话） | (streaming run) |
| research.chat.templateSection | 请解释这一节：核心思想是什么？它是如何工作的？ | Explain this section: what is the key idea and how does it work? |
| research.chat.templatePaper | 请解读这篇论文：TL;DR、方法、结果与局限。 | Explain this paper: TL;DR, method, results, and limitations. |
| research.chat.templateIdea | 帮我发展这个想法：可行的实验方案和潜在风险是什么？ | Help me develop this idea: what experiments and risks should I consider? |
| research.chat.templateGap | 围绕这个研究空白，帮我起草一个具体的研究想法。 | Draft a concrete research idea around this gap. |
| research.chat.suggestSummarize | 总结《{title}》 | Summarize "{title}" |
| research.chat.suggestConnect | 我最近的论文之间有什么联系？ | What connects my recent papers? |
| research.chat.suggestIdea | 挑战我的想法「{title}」 | Stress-test my idea "{title}" |
| research.chat.suggestSearch | 先去搜索一些论文 → | Search for papers first → |
| research.ideas.title | 想法 | Ideas |
| research.ideas.new | 新想法… | New idea… |
| research.ideas.empty | 还没有想法 | No ideas yet |
| research.ideas.generate | 从文库生成想法 | Generate ideas from library |
| research.ideas.generating | 正在挖掘研究空白… | Mining research gaps… |
| research.ideas.needPapers | 至少导入 3 篇论文后可用 | Import at least 3 papers first |
| research.ideas.runCritic | 运行评审 | Run critic |
| research.ideas.reviewing | 评审中… | Reviewing… |
| research.ideas.develop | 发展这个想法 | Develop this idea |
| research.ideas.archive | 归档 | Archive |
| research.ideas.novelty | 新颖度 {score} | Novelty {score} |
| research.ideas.gapCoverage | 覆盖空白 | Coverage gap |
| research.ideas.gapLimitation | 局限跟进 | Limitation follow-up |
| research.ideas.gapTransfer | 跨域迁移 | Cross-domain transfer |
| research.ideas.support | 支撑文献 | Supporting papers |
| research.ideas.listView | 列表 | List |
| research.ideas.matrixView | 矩阵 | Matrix |
| research.ideas.matrixEmpty | 先生成想法，矩阵才会出现。 | Generate ideas first to build the matrix. |
| research.ideas.draftIdea | 为此空白起草想法 | Draft idea for this gap |
| research.critic.title | 评审意见 | Critic review |
| research.critic.weaknesses | 弱点 | Weaknesses |
| research.critic.missingBaselines | 缺失基线 | Missing baselines |
| research.critic.datasetRisks | 数据风险 | Dataset risks |
| research.critic.reproducibility | 可复现性 | Reproducibility |
| research.common.notAvailable | 该功能的后端尚未就绪 | Backend for this feature is not ready yet |
| research.common.retry | 重试 | Retry |

(`{n}`/`{title}`-style placeholders are simple `.replace()` interpolations done at the call site — the i18n lib has no interpolation (ARCHITECTURE_MAP #64); helper `interp(t(key), vars)` lives in `features/research/citations.ts`… no — in a 6-line local util inside `ResearchWorkspace.tsx`, exported for the partition.)
