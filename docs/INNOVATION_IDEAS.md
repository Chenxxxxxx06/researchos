# ResearchOS Innovation Ideas — Judged, Merged, and Prioritized

Synthesized from three independent ideation lenses (ALGORITHM DEPTH, UX/PRODUCT, SYSTEMS-INTEGRATION)
against the owner's 8-point wishlist. This document is the canonical input for design-spec agents:
every idea retains its complete algorithm sketch.

- Date: 2026-07-26
- Source lens counts: 13 (algorithms) + 12 (UX/product) + 12 (systems) = 37 raw ideas → 33 after merging.
- Scoring: `impact` 1–5 (5 = transformative), `feasibility_now` 1–5 (5 = implementable this session with no
  external services or long quality iteration), `priority = impact × feasibility`.
- Ideas with impact ≥ 4 but feasibility ≤ 3 also appear in the **Transformative Bets** section — do not drop
  them just because their priority number is low; they are the moat.
- `[NOW]` = implementable-this-session (possibly phased; the NOW phase is called out where relevant).

---

## Priority Summary (all workstreams)

| # | Idea | WS | Impact | Feas | Priority | NOW? |
|---|------|----|--------|------|----------|------|
| 1 | Coding agent eyes: read/grep tools + per-type budget + read-before-write enforcement | WS2 | 5 | 5 | 25 | YES |
| 2 | Named Result Anchors (\newcommand macros from run metrics) | WS3 | 5 | 5 | 25 | YES |
| 3 | arXiv Query Compiler (fielded queries, categories, dates, pagination) | WS1 | 4 | 5 | 20 | YES |
| 4 | Multi-source federation (S2 + OpenAlex + Crossref + dedup) | WS1 | 5 | 4 | 20 | YES |
| 5 | Structured full-text ingestion (ar5iv/HTML sections + PDF fallback) | WS1 | 5 | 4 | 20 | YES |
| 6 | Diff-native patches: search/replace hunks + per-hunk accept | WS2 | 5 | 4 | 20 | YES |
| 7 | Git-backed workspace: commit per patch, branches, revert timeline | WS2 | 5 | 4 | 20 | YES |
| 8 | Coding chat with inline diff cards (chat-to-diff) | WS2 | 5 | 4 | 20 | YES |
| 9 | Overleaf-grade LaTeX editor core | WS4 | 4 | 5 | 20 | YES |
| 10 | Floating selection assistant with tracked changes | WS4 | 5 | 4 | 20 | YES |
| 11 | Semantic design tokens + dark mode + theme-aware Monaco/Recharts | WS7 | 4 | 5 | 20 | YES |
| 12 | Command palette (Ctrl+K) + keyboard-first navigation | WS7 | 4 | 5 | 20 | YES |
| 13 | pgvector embeddings + library-centroid personalized ranking | WS1 | 4 | 4 | 16 | YES |
| 14 | Repo map context for the coding agent | WS2 | 4 | 4 | 16 | YES |
| 15 | Self-verifying patches (compile/lint gate + bounded auto-repair) | WS2 | 4 | 4 | 16 | YES |
| 16 | Run telemetry contract (NDJSON ingest + run tokens + client shim) | WS3 | 4 | 4 | 16 | YES |
| 17 | Staleness sentinel (new run supersedes paper numbers) | WS3 | 4 | 4 | 16 | YES |
| 18 | Figure worker (matplotlib → MinIO → \begin{figure}) | WS3 | 4 | 4 | 16 | YES |
| 19 | Run-comparison LaTeX table generator + paper-asset inbox | WS3 | 4 | 4 | 16 | YES |
| 20 | Real PDF compile preview with error-to-line mapping | WS4 | 4 | 4 | 16 | YES |
| 21 | Skill runtime injection with tool-permission broker | WS8 | 4 | 4 | 16 | YES |
| 22 | Paper reading room + Paper Tutor (phased) | WS1 | 5 | 3 | 15 | v1 YES |
| 23 | Sandboxed execution runner (real jobs, smoke runs, real LaTeX) | WS6 | 5 | 3 | 15 | scaffold YES |
| 24 | Provenance graph + "where did this number come from?" panel | WS8 | 5 | 3 | 15 | YES (after deps) |
| 25 | Unified agent run inspector | WS7 | 3 | 5 | 15 | YES |
| 26 | Golden-path onboarding checklist + actionable empty states | WS7 | 3 | 5 | 15 | YES |
| 27 | Freshness daemon: per-project arXiv watch feeds | WS1 | 4 | 3 | 12 | after deps |
| 28 | Figure style presets as skills + settings surface (merged) | WS3 | 3 | 4 | 12 | YES |
| 29 | Gap-matrix idea generation | WS5 | 5 | 2 | 10 | no — iteration |
| 30 | Research pipelines (idea → smoke run → paper DAG) | WS8 | 5 | 2 | 10 | no — iteration |
| 31 | Novelty gauntlet (propose → search → score → revise loop) | WS5 | 4 | 2 | 8 | no — iteration |
| 32 | Related-work weaver (library → cited prose patch) | WS4 | 4 | 2 | 8 | no — iteration |
| 33 | SSH smoke-test runtime (approval-gated remote execution) | WS6 | 4 | 2 | 8 | no — external |

---

## WS1 — Paper Ingestion, Search & Reading
**Owner scope:** wishlist 1 (fetching/extraction) and 2 (analyze/explain/teach). One engineer owns the provider
layer, the ingestion pipeline, embeddings, the feed, and the reading UX.
**Suggested order:** Query Compiler → Federation → Full-text ingestion → pgvector → Reading room v1 → Freshness feed → Tutor v2.

### WS1-1. arXiv Query Compiler: fielded queries, categories, date windows, pagination
- Source: ALGO lens. Impact 4 · Feasibility 5 · **Priority 20** · `[NOW]` · Depends on: —
- **Problem:** `apps/api/researchos/research/providers/arxiv.py` builds exactly one request:
  `search_query=all:{query}, start=0, sortBy=relevance`. `PaperSearchFilters` (base.py) defines
  year_from/year_to but the provider never reads the filters argument, and the REST router never passes
  filters. No category filtering, no freshness sort, no pagination past the first page — so "latest papers in
  cs.LG on diffusion" is impossible to express.
- **Proposal:** Replace the raw string with a small query-AST compiler inside ArxivProvider, extend
  PaperSearchFilters to carry categories/date-window/sort/page, and add an optional LLM "query planner" step
  that translates the user's natural-language query into the structured filter object before the provider is
  called.
- **Algorithm sketch:**
  1) Extend PaperSearchFilters: `{year_from, year_to, categories: list[str] (e.g. ['cs.LG','cs.CL']), date_from: date|None, date_to: date|None, sort: 'relevance'|'latest', offset: int, fields: {title: str|None, abstract: str|None, author: str|None}}`.
  2) In ArxivProvider.search, compile to arXiv syntax: `terms = []`; if fields.title: `terms.append(f'ti:"{v}"')`; same for `abs:`/`au:`; free text → `all:{query}`; categories → `(cat:cs.LG OR cat:cs.CL)`; date window → `submittedDate:[YYYYMMDDHHMM TO YYYYMMDDHHMM]`; join with AND.
  3) Map sort: latest → `sortBy=submittedDate&sortOrder=descending`; pass `start={offset}&max_results={limit}` for pagination.
  4) Router change: POST `/projects/{id}/research/papers/search` body gains a `filters` object mirroring PaperSearchFilters; frontend adds a filter bar (category multiselect from a static arXiv taxonomy JSON, year range slider, sort toggle, "load more" using offset).
  5) Optional planner: before provider call, if filters absent and query is natural language, one LLM call with response_schema = PaperSearchFilters JSON schema + a cleaned keyword string; on MockLLMProvider this step is skipped (pass-through), so it degrades safely.
  6) Unit tests extend the existing recorded-fixture pattern in test_paper_search.py with fixtures for fielded queries.

### WS1-2. Multi-source federation: Semantic Scholar + OpenAlex + Crossref with cross-source dedup
- Source: ALGO lens. Impact 5 · Feasibility 4 · **Priority 20** · `[NOW]` · Depends on: —
- **Problem:** `providers/registry.py` hard-codes a single provider ('arxiv'); `PaperService.import_papers`
  dedups only on (project_id, source, external_id), so the same paper found via two sources would create two
  library rows. No citation counts, no venue metadata, no coverage of non-arXiv venues.
- **Proposal:** Implement OpenAlexProvider, SemanticScholarProvider, CrossrefProvider against the existing
  PaperSearchProvider protocol (all three have keyless public APIs), add a FederatedProvider that fans out
  concurrently and merges, and a three-tier dedup pass (DOI, arXiv id, fuzzy title+author) that also enriches
  merged records with citation counts.
- **Algorithm sketch:**
  1) New providers, each ~100 lines mirroring arxiv.py: OpenAlex `GET https://api.openalex.org/works?search={q}&per-page={n}&mailto=...` (maps ids.doi, primary_location.source.display_name → venue, cited_by_count → extra); Semantic Scholar `GET https://api.semanticscholar.org/graph/v1/paper/search?query={q}&fields=title,abstract,externalIds,year,venue,citationCount,openAccessPdf` (keyless, rate-limited ~1 rps — add a Redis token-bucket reusing common/rate_limit.py); Crossref `GET https://api.crossref.org/works?query={q}`.
  2) Extend PaperResult with `doi: str|None` and `citation_count: int|None` (store doi also in metadata_json for the existing Paper model — no migration needed initially; later add a doi column + index).
  3) FederatedProvider.search: asyncio.gather over enabled providers with per-provider timeout; failures degrade to partial results (log, don't raise).
  4) Dedup pipeline over the concatenated list: key1 = normalized DOI (lowercase, strip https://doi.org/); key2 = arXiv id (OpenAlex/S2 expose it in externalIds); key3 = (normalize_title(t), first_author_lastname) where normalize_title = lowercase, strip punctuation/whitespace, NFKD fold — union-find merge, prefer arXiv record as canonical (has pdf_url), fold citation_count and venue from the richer source into extra.
  5) import_papers: before insert, check library not just by (source, external_id) but also by doi and by arXiv id found in metadata_json of the incoming record.
  6) Settings: paper_provider becomes `paper_providers: list[str] = ['arxiv','openalex']`; registry returns FederatedProvider when len>1.
  7) UI: source badges + citation-count column in search results.

### WS1-3. Structured full-text ingestion: ar5iv/arXiv-HTML section extractor with PDF fallback
- Source: ALGO lens. Impact 5 · Feasibility 4 · **Priority 20** · `[NOW]` · Depends on: —
- **Problem:** The Paper model (research/models.py) stores only title/abstract/url/pdf_url — no full text, no
  sections. Every downstream feature (explanation, teaching, idea generation, related-work synthesis) can only
  see the abstract, which caps quality hard.
- **Proposal:** A Celery ingestion task that, on paper import, fetches the paper's HTML rendering
  (ar5iv.labs.arxiv.org/html/{id} or arxiv.org/html/{id} for post-2023 papers), parses it into a typed section
  tree, falls back to pypdf text extraction for non-arXiv PDFs, and persists a paper_sections table that agents
  can query section-by-section.
- **Algorithm sketch:**
  1) New table `paper_sections`: `{id, paper_id FK, seq int, level int, heading str, body text, char_count int, kind enum('abstract','intro','method','experiments','related','conclusion','appendix','other')}`. Migration 000N.
  2) Celery task `research.ingest_fulltext(paper_id)` enqueued at the end of PaperService.import_papers.
  3) Fetch chain: (a) if source=='arxiv': GET `https://arxiv.org/html/{id}v{latest}` then ar5iv fallback; parse with BeautifulSoup: `sections = soup.select('section')`, heading from h2/h3, strip MathML to LaTeX-ish text via alttext attrs; (b) else if pdf_url: download to MinIO (common/storage.py already wraps it), extract per-page text with pypdf, split into pseudo-sections on regex `^(\d+\.?\s+[A-Z][^\n]{3,60})$`; (c) else mark status='abstract_only'.
  4) kind classification: keyword map on heading (intro/method/experiment/related/conclusion), default 'other' — deterministic, no LLM needed.
  5) New tool in TOOL_REGISTRY: `paper.sections(paper_id, kind?|seq?)` returning `[{seq, heading, body[:2000]}]` so ResearchAgent can pull specific sections under the citation whitelist (whitelist key stays source:external_id).
  6) Paper detail page renders the section tree with an ingestion-status chip.
  7) GROBID (as an extra docker-compose service) is a drop-in upgrade later for reference parsing — not required for v1.

### WS1-4. Wake the sleeping pgvector: embedding search + library-centroid personalized ranking
- Source: ALGO lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: —
- **Problem:** infra/docker/docker-compose.yml already runs pgvector/pgvector:pg16, but grep confirms zero
  vector columns or embedding code anywhere in apps/api. Search ranking is whatever arXiv returns; the library
  teaches the system nothing about the user's taste.
- **Proposal:** Add an embeddings adapter to the existing LLM provider layer (OpenAI-compatible /embeddings
  endpoint; deterministic hashed-BoW fallback under MockLLMProvider), embed every library paper's
  title+abstract into a pgvector column, and re-rank all provider search results by a blend of provider rank
  and cosine similarity to the project's library centroid.
- **Algorithm sketch:**
  1) Migration: `CREATE EXTENSION IF NOT EXISTS vector; ALTER TABLE papers ADD COLUMN embedding vector(1536);` ivfflat index cosine.
  2) agents/llm gains `embed(texts: list[str]) -> list[list[float]]`: OpenAI-compatible POST /embeddings using the project's existing per-project LLM config; MockLLMProvider implements a seeded feature-hash of token unigrams into 1536 dims (deterministic, testable offline).
  3) Celery task `research.embed_paper(paper_id)` on import; backfill command `python -m researchos.seed.embed_backfill`.
  4) Personalized rank at search time in PaperService.search: centroid = AVG(embedding) over project library (one SQL with pgvector AVG, cached in Redis 10 min); for each provider result, embed on the fly (batch, one call), `score = 0.6 * reciprocal_rank(provider_position) + 0.4 * cosine(result_emb, centroid)`; return sorted with score exposed as `extra['personal_score']` so the UI can show a "fits your library" bar.
  5) New endpoint `GET /projects/{id}/research/papers/{paper_id}/similar` → `SELECT ... ORDER BY embedding <=> :vec LIMIT 10` for a "related in your library" panel.
  6) Cold-start (empty library): blend weight collapses to provider order — no behavior change.

### WS1-5. Paper reading room + Paper Tutor (merged, phased)
- **Merged from:** UX "Paper reading room: side-by-side PDF + streaming AI explanation" + ALGO "Paper Tutor:
  progressive-depth, section-grounded explanation agent with quizzes".
- Impact 5 · Feasibility 3 (v1 reading room = 4/NOW; v2 tutor = needs-long-iteration) · **Priority 15** ·
  `[NOW: phase 1]` · Depends on: WS1-3 (for grounded depth; v1 works abstract-only).
- **Problem:** PaperLibrary.tsx renders saved papers as `<a target="_blank">` links straight out to arxiv.org —
  no in-app reading experience at all, so the "analyze/explain/teach papers" wishlist item has no UX surface.
  ResearchAgent (runtime/research_agent.py) is a single-shot synthesizer over abstracts with a citation
  whitelist — there is no way to "teach me this paper", no depth control, and nothing grounds explanations in
  actual paper content because full text isn't ingested.
- **Proposal:** Phase 1 (NOW): clicking a library paper opens a reading route — left pane renders the arXiv PDF
  (proxied through the backend to dodge CORS), right pane streams a structured explanation (TL;DR, Method,
  Results, Limitations, Why-it-matters-for-this-project) and supports select-text-in-PDF → "Explain this"
  threaded Q&A anchored to the paper. Phase 2 (iteration): a new EXPLAIN agent type that walks a single paper
  section-by-section at a user-chosen depth level (undergrad / practitioner / expert), where every explanation
  block must quote a span from a real ingested section (extending the whitelist mechanism from paper ids to
  section anchors), plus a quiz generator whose answer key cites section seq numbers.
- **Algorithm sketch (phase 1 — reading room):**
  1) Backend: `GET /projects/{id}/papers/{paperId}/pdf` → httpx fetch of the paper's PDF URL, cached on disk keyed by source:external_id, streamed as application/pdf.
  2) New route `research/read/[paperId]`: left pdfjs-dist viewer with text layer enabled; right ExplanationPanel.
  3) On first open: createAgentRun `{agent_type:'research', message: explain-paper directive + title/abstract/external_id}`; render the streamed output into section cards by parsing `## ` headings from the response; cache via input_json.paper_id so revisits show the persisted run instead of re-spending tokens.
  4) Explain-selection: pdf.js text-layer selection → floating "Explain" chip → agent run with `{selection, paper_id, page}`; answers append to a per-paper Q&A thread (agent runs filtered client-side on input_json.paper_id).
  5) Citation chips in explanations reuse the existing whitelist mechanism.
  6) When full-text extraction (WS1-3) lands, the same runs receive parsed section text instead of abstract-only context — UI unchanged, depth improves.
- **Algorithm sketch (phase 2 — tutor):**
  1) New AgentType.EXPLAIN registered in runtime.py `_AGENTS`; allowed_tools = ['paper.sections', 'library.list']. Input context: `{paper_id, depth: 1|2|3, mode: 'walkthrough'|'quiz'|'summary'}`.
  2) build_messages: system prompt parameterized by depth (depth 1: analogies, no math, define every term; depth 2: keep equations, focus on how to implement; depth 3: assumptions, limitations, relation to sota) + hard rule: every claim block ends with a grounding tag `[[sec:{seq}]]` quoting <=200 chars verbatim.
  3) Walkthrough loop: agent calls paper.sections(kind='method') etc.; runtime emits one WebSocket 'section_explained' event per section so the frontend renders a step-through UI (Prev/Next) instead of a wall of text — reuses the existing Redis pub/sub event pipeline (websocket/envelopes.py).
  4) finalize: validate every `[[sec:N]]` tag against the sections actually fetched in tool_ctx (extend citation whitelist keys to 'arxiv:2401.01234#sec:5'); strip claims whose tags fail — the existing filter_citations pattern generalizes directly.
  5) Quiz mode: response_schema = `{questions: [{q, choices[4], answer_idx, why, section_seq}]}`; frontend renders interactive quiz, grades locally, "show source" jumps to the section in the paper detail pane.
  6) Quality iteration: prompt depth calibration and quote-fidelity need repeated testing against real papers with a real LLM key — mock provider can only verify plumbing.

### WS1-6. Freshness daemon: per-project arXiv watch feeds ranked by library fit
- Source: ALGO lens. Impact 4 · Feasibility 3 · **Priority 12** · Depends on: WS1-1, WS1-4.
- **Problem:** There is no notion of "new since yesterday" anywhere — search is pull-only and relevance-sorted
  (arxiv.py hard-codes sortBy=relevance). Wishlist item 1 explicitly asks for latest-paper fetching; Celery +
  Redis already exist but no beat schedule is defined.
- **Proposal:** A Celery-beat job per project that queries arXiv with sortBy=submittedDate over categories
  inferred from the project library, dedups against the library and prior feed items, ranks by centroid
  similarity, and lands results in a new "Feed" tab with one-click import.
- **Algorithm sketch:**
  1) New table `feed_items`: `{id, project_id, source, external_id, title, abstract, url, pdf_url, published_at, score float, status enum('new','seen','imported','dismissed'), created_at}` unique(project_id, source, external_id).
  2) Category inference: collect metadata_json['arxiv_primary_category'] (start storing it in ArxivProvider from entry.arxiv_primary_category) over the library; take categories covering >=80% of papers, else default from a project setting.
  3) Beat task `research.refresh_feed` nightly per project: for each category run the Query Compiler with sort='latest', date_from=last_run, max 100 via pagination; alternative transport: arXiv RSS (rss.arxiv.org/rss/{cat}) parsed by the already-imported feedparser — cheaper than the API for pure freshness.
  4) Dedup: skip ids already in papers or feed_items (same three-tier keying as the federation dedup).
  5) Score with the library-centroid cosine from WS1-4; store top-K (K=30), discard below threshold 0.15.
  6) API: `GET /projects/{id}/research/feed?status=new`, `POST .../feed/{item_id}/import` (delegates to import_papers), `POST .../dismiss`.
  7) UI: Feed tab with score bars; importing a feed item is implicit positive feedback — recompute centroid, so the feed self-tunes.
  8) Digest hook later: weekly summary via the research agent.

---

## WS2 — Agentic Coding & Git
**Owner scope:** wishlist 5 (chat maps directly to diffs, git rollback/traceability) and 6 (NL→code quality).
One engineer owns the coding agent, patch format/verification, git layer, and the coding chat UI.
**Suggested order:** Read tools → Hunk patches → Repo map → Git workspace → Coding chat → Self-verification.

### WS2-1. Coding agent eyes: workspace.read + workspace.grep + per-type tool budget + read-before-write enforcement
- **Merged from:** ALGO "Read-before-write: workspace.read + workspace.grep tools and a real tool budget" +
  UX "Give the coding agent eyes" (tools portion).
- Impact 5 · Feasibility 5 · **Priority 25** · `[NOW]` · Depends on: —
- **Problem:** CodingAgent (runtime/coding_agent.py) has `allowed_tools=['workspace.tree']` — it literally
  cannot read file contents, yet is asked to emit whole-file new_content, so every "modify" patch is
  hallucinated from the file name. Meanwhile WorkspaceService.read_file already exists as a REST endpoint
  (workspace/router.py) — it just was never wrapped as a tool. `agent_max_tool_calls=4` globally makes
  multi-file work impossible even if it could read.
- **Proposal:** Add workspace.read(path) and workspace.grep(pattern, glob) to TOOL_REGISTRY, grant them to
  CodingAgent, raise its tool budget to ~25 via a per-agent-type override, and enforce a finalize-time rule:
  any "modify" file whose path was never read this run is rejected with a structured error the agent sees,
  forcing the read-before-write discipline.
- **Algorithm sketch:**
  1) tools.py: `_workspace_read(ctx, args)` → `WorkspaceService(ctx.db).read_file(ctx.actor, ctx.project_id, args['path'])` returning `{path, content, sha}` (sha already computed by common/hashing.py for the base_sha guard — return it so the agent can echo it back as base_sha); `_workspace_grep`: walk workspace root via common/paths.resolve_in_workspace, regex over files matching glob, return `[{path, line_no, line}]` capped at 50–100.
  2) `CodingAgent.allowed_tools = ['workspace.tree','workspace.read','workspace.grep']`; extend the `_SYSTEM` prompt: "read any file before modifying it; set base_sha from the read result".
  3) Settings: agent_max_tool_calls becomes dict per AgentType `{coding: 25, default: 4}`; runtime.py reads the per-type value.
  4) Track reads in ToolContext: `read_paths: dict[path -> sha]` populated by `_workspace_read`.
  5) finalize: for each 'modify'/'delete' file, require `raw['path'] in tool_ctx.read_paths` and base_sha == read sha; violations are collected and, instead of silently dropping (current behavior drops invalid paths!), the run appends a tool-style message listing violations and loops once more so the agent can fix itself — one extra iteration, bounded.
  6) Also fixes a latent runtime bug to make multi-turn tool use sound: `_run_loop` appends `LLMMessage(role='assistant', content='')` before tool results, discarding the assistant's tool_use block — Anthropic's API requires the tool_use content to round-trip; persist the actual assistant turn.
  7) Payoff is immediate and user-visible: modify patches diff cleanly against real content instead of rewriting files from guesswork.

### WS2-2. Diff-native patches: search/replace hunks + server-computed hunks + per-hunk accept
- **Merged from:** ALGO "Search/replace hunk patches: diff-based edits instead of whole-file rewrites" +
  UX "Give the coding agent eyes" (hunk-level diffs and per-hunk accept portion).
- Impact 5 · Feasibility 4 · **Priority 20** · `[NOW]` · Depends on: WS2-1.
- **Problem:** PatchFileInput (patches/schemas.py, used by coding_agent.py finalize) carries only
  new_content — full file text. For any file over ~200 lines the LLM must reproduce the entire file perfectly,
  which is the single biggest source of corrupted patches in whole-file systems; it also bloats tokens and
  makes the review diff noisy. Additionally, the PatchHunk table (patches/models.py: header, old_start,
  old_lines, new_start, new_lines, content) already exists in the schema but nothing ever populates it, and
  apply_patch is all-or-nothing whole-file replacement.
- **Proposal:** Extend the patch format with Aider-style search/replace hunks: the agent emits
  `[{search, replace}]` blocks per file; the server resolves them against the real base content (exact match,
  then whitespace-insensitive, then fuzzy), materializes new_content server-side, and keeps the existing
  base_sha guard and review flow untouched. On proposal creation, also compute real unified-diff hunks into
  the existing PatchHunk rows and let the user accept/reject individual hunks in the review UI.
- **Algorithm sketch (agent-side search/replace):**
  1) Schema: PatchFileInput gains `edits: list[{search: str, replace: str}] | None`; exactly one of new_content / edits required ('create' keeps new_content).
  2) Resolution algorithm in PatchService.create_proposal: load base content via WorkspaceService.read_file, verify sha == base_sha; for each hunk: (a) exact substring match; (b) fallback: line-wise match ignoring trailing whitespace and indentation-only differences; (c) fallback: difflib.SequenceMatcher best window with ratio >= 0.9; require unique match — 0 or >1 matches → structured error `{file, hunk_idx, reason: 'not_found'|'ambiguous'}`.
  3) Apply hunks sequentially to produce new_content; store BOTH the resolved new_content (so apply/review paths are unchanged) and the raw hunks in a new hunks_json column for traceability.
  4) CodingAgent system prompt/response_schema updated: modify → emit edits with >=3 lines of context in each search block; create → new_content.
  5) Resolution errors are fed back into the run loop as a tool-result message (same bounded retry as the read-before-write rule) so the agent re-anchors its hunks.
  6) Token cost drops ~10x on modifications and eliminates the truncated-file failure mode.
- **Algorithm sketch (server-side hunks + per-hunk accept):**
  1) PatchService.create_proposal: for change_type=modify with existing base, run `difflib.unified_diff(old_lines, new_lines, n=3)`, parse `@@` headers into PatchHunk rows.
  2) API: GET patch now returns `files[].hunks[]`; `POST /patches/{id}/apply` accepts optional body `{selections:[{file_id, hunk_ids:[...]|'all'}]}`.
  3) Apply algorithm: verify base_sha per file; materialize selected hunks against base content in ascending old_start order tracking line-offset delta (hunks derive from the exact same base, so application is deterministic); write via fs.write_file; unselected hunks are dropped and recorded in ApplyResult as skipped.
  4) Frontend PatchDiff hunk mode: one card per hunk (checkbox, mini read-only Monaco diff of just that region ±3 lines), "Apply 3 of 5 hunks" button; falls back to whole-file view when hunks are absent (create/delete). Optionally badge each file with hunk count.

### WS2-3. Git-backed workspace: commit per applied patch, agent branches, revert timeline
- **Merged from:** UX "Real git checkpoints per agent turn + rollback timeline" + SYS "Git-backed workspace:
  commit per applied patch, branch per agent session, revert UI".
- Impact 5 · Feasibility 4 · **Priority 20** · `[NOW]` · Depends on: — (pairs naturally with WS2-4).
- **Problem:** git/provider.py ships StubGitStatusProvider (always reports clean, files=[]); GitStatusPanel.tsx
  renders the fake branch/clean pill. Workspace files live on plain disk (workspace/fs.py
  write_file/delete_file) with zero versioning: applying an agent patch writes straight to disk with only a
  base_sha conflict guard, PatchProposal has no record of what the workspace looked like after apply, and
  rollback is impossible — violating wishlist 5's git-backed rollback/traceability requirement.
- **Proposal:** Make every workspace a real git repo (dulwich, pure Python — no git binary in the API image).
  Every patch apply and every manual save becomes a commit tagged with agent_run_id/patch_id;
  agent-originated patches land on an `agent/{run_id}` branch merged on user acceptance; a Checkpoint
  Timeline / History panel in the IDE lists commits with linked patch/agent chips, per-commit diff view, and a
  safe revert (inverse commit, never history rewrite — honoring the PHASE3-D10 no-destructive-ops rule).
  GitStatusPanel becomes real.
- **Algorithm sketch:**
  1) ensure_workspace(): if no .git, initialize via dulwich with committer 'researchos-bot', seeding .gitignore.
  2) GitService methods: status(), log(limit, path?), diff(sha), commit(paths, message), branch(name), revert(sha) — all cwd-locked to the workspace root with 5s timeouts.
  3) Patch apply flow change (patches service): if proposal.agent_run_id, checkout-or-create branch `agent/{run_id}`; write files; commit `'patch {short_id}: {summary}\n\nAgent-Run: {run_id}'`; store new column PatchProposal.applied_commit_sha (one Alembic migration). Manual document saves commit as `'[manual] edit {path}'`.
  4) Replace the stub: RealGitStatusProvider parses status (dulwich porcelain) into the existing GitStatusResponse schema (git/schemas.py) — branch, clean, files[{path, state}].
  5) Endpoints: `GET /projects/{pid}/git/log` → `[{sha, message, ts, patch_id?, agent_run_id?}]` (last 50 via walker, ids parsed from commit-message trailers); `GET /git/commits/{sha}/diff` (per-file old/new content pairs for MonacoDiff); `POST /git/revert {sha}` allowed only on a clean tree, creates the inverse commit (restores that tree via a new commit — never reset).
  6) IDE UI: vertical Checkpoint Timeline / History panel in the left rail below the file tree — dot per commit, agent vs user icon, relative time, summary; click → diff sheet; Restore/Rollback button with diff-preview confirm modal; chips deep-link to patch diff and the agent conversation. "Accept session" merges the agent branch to main; conflicts surface as a fresh PatchProposal. Coding-chat DiffCards (WS2-4) show their checkpoint sha and a "roll back to before this change" shortcut.
  7) GitStatusPanel lists real dirty files with per-file diff on click.
  8) ExperimentRun.git_commit (already a column) is set from HEAD at launch, closing the code-version loop.

### WS2-4. Coding chat thread with inline diff cards (Cursor-style chat-to-diff)
- Source: UX lens. Impact 5 · Feasibility 4 · **Priority 20** · `[NOW]` · Depends on: — (enhanced by WS2-2/WS2-3).
- **Problem:** apps/web/features/ide/CodingAssistant.tsx is a one-shot textarea, not a chat: it fires
  createCodingRun then polls by invalidating the patches query five times on setTimeout(i*1200ms). The
  resulting patch appears in a physically separate PatchReviewPanel with no visual link back to the request, no
  streaming, and no conversation history — even though the backend already persists agent_runs, streams
  agent.run.token events over WebSocket (events.py), and stores patch.agent_run_id linking every patch to its
  run.
- **Proposal:** Replace CodingAssistant + PatchReviewPanel with a single persistent CodingChat pane modeled on
  ResearchChat.tsx: user bubbles, live-streamed agent text, tool-call chips, and — when a run completes with
  output_json.patch_id — an inline DiffCard embedded in the assistant bubble showing per-file Monaco diffs with
  Apply/Reject buttons right in the conversation. The card's status badge (pending/applied/rejected/conflict)
  updates in place, so the chat IS the change history.
- **Algorithm sketch:**
  1) Backend: no new tables — agent_runs, patches.agent_run_id, and output_json.patch_id already exist; optionally add `?agent_run_id=` filter to `GET /projects/{id}/patches`.
  2) Frontend CodingChat.tsx: query listAgentRuns filtered to agent_type==='coding' (persisted history) + useProjectAgentEvents for live runs; render per run: user bubble (input_json.message), streaming text from agent.run.token deltas, ToolCallChip rows, then `<PatchCard patchId={output_json.patch_id}>`.
  3) PatchCard: useQuery(['patch', patchId]) → header (summary, N files, status pill), body reuses existing PatchDiff per file, footer Apply/Reject reusing lib/api/patches mutations; on apply success invalidate ['workspace-tree'], ['file'], and show conflict list inline (ApplyResult.conflicts already returned).
  4) Delete the setTimeout polling — the agent.run.completed WS event payload triggers a single patch fetch.
  5) Keep a compact "Changes" filter tab listing only runs that produced patches.

### WS2-5. Repo map context: ranked signature skeleton injected into the coding agent
- Source: ALGO lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: WS2-1.
- **Problem:** CodingAgent starts every run knowing nothing but the user message; its first (and often only,
  budget=4) tool call is workspace.tree, which returns names with no idea what's inside. There is no repo-level
  context builder anywhere in apps/api — the agent cannot know that PatchService lives in patches/service.py
  without reading files one by one.
- **Proposal:** An Aider-style repo map, built server-side without tree-sitter: Python files parsed with the
  stdlib ast module into class/def signatures + docstring first lines; TS/JS via regex heuristics; files ranked
  by import-graph centrality plus query-term overlap; the top slice (token-budgeted) injected into
  CodingAgent.build_messages as a system-message appendix, cached and invalidated on patch apply.
- **Algorithm sketch:**
  1) New module workspace/repomap.py: build_map(project_id) walks workspace files (reuse resolve_in_workspace guards); for .py: ast.parse → for each top-level class/def emit `'path:lineno: def f(a, b) -> str — first docstring line'`; for .ts/.tsx/.js: regex for `export (function|const|class|interface) NAME(...)`.
  2) Ranking: build directed import graph (Python: ast Import/ImportFrom mapped to workspace paths; TS: `import ... from './x'`); `score = 0.5 * pagerank(graph) + 0.3 * term_overlap(user_message tokens, path+symbol names) + 0.2 * recency(file mtime rank)`.
  3) Emit map greedily by file score until ~2000 token budget (len/4 estimate); always include files literally named in the user message.
  4) Cache the parsed skeleton per file keyed by content sha in Redis; invalidate on PatchService.apply.
  5) CodingAgent.build_messages appends: `'Repo map (signatures only, read files before editing):\n{map}'`.
  6) Measurable payoff: agent's first tool call becomes a targeted workspace.read instead of blind tree listing; combine with the 25-call budget for real multi-file navigation.
  7) API surface: none new (internal), plus optional `GET /projects/{id}/workspace/repomap` for the IDE to render an outline panel — one algorithm, two features.

### WS2-6. Self-verifying patches: compile/lint gate with bounded auto-repair before human review
- Source: ALGO lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: WS2-2.
- **Problem:** A coding-agent patch goes straight from LLM output to the user's review queue
  (patches/service.py create_proposal) — nothing ever checks that the proposed Python even parses. The user is
  the first syntax checker, which wastes the review loop on trivial breakage and undermines wishlist item 6
  (NL→code quality).
- **Proposal:** After create_proposal, a Celery verification task materializes the patched files into a shadow
  directory, runs cheap deterministic checks (Python: compile() via ast, ruff if available; TS: tsc --noEmit
  optional; JSON/YAML: load), attaches a verification_report to the proposal, and on failure feeds the errors
  back to the agent for at most 2 repair iterations before surfacing to the human with the report visible in
  the review UI.
- **Algorithm sketch:**
  1) Patch model gains verification_json: `{status: 'passed'|'failed'|'skipped', checks: [{file, tool: 'pyast'|'ruff'|'json', ok, messages: [{line, msg}]}], attempts: int}`.
  2) Task patches.verify(patch_id): copy only affected files + their imports-closure (from the repo-map graph, depth 1) into scratchdir; overlay new_content; per file type run: Python → ast.parse (in-process, no shell needed — safe in the no-shell container policy) + optional subprocess `ruff --output-format json` when the binary exists; JSON/YAML/TOML → stdlib/parser load; else skip.
  3) On failure and attempts < 2: construct a repair AgentRun whose input message = original request + serialized errors + current hunks, reusing the normal CodingAgent path; the repair run's proposal supersedes (links superseded_by on the old one).
  4) On pass or attempts exhausted: status set, WebSocket event 'patch_verified' → review UI shows a green check or the error list inline per file.
  5) Ordering guarantee: verification never blocks proposal creation (report arrives async); apply is allowed regardless — the gate informs, the human decides, matching the existing propose-review-apply permission model.
  6) This is the minimal seed of the full test-running loop: the check-runner interface (`{file_types, run(files) -> messages}`) later accepts pytest-in-sandbox when real execution lands (WS6-1).

---

## WS3 — Experiment→Paper Binding & Figures
**Owner scope:** wishlist 7 (results flow into the paper, styled figures, style settings). One engineer owns
telemetry ingest, result anchors, staleness, the figure worker, style skills, and the asset inbox.
**Suggested order:** Result anchors → Telemetry contract → Staleness → Figure worker → Table generator/inbox → Style presets.

### WS3-1. Named Result Anchors: \newcommand macros auto-regenerated from run metrics
- Source: SYS lens. Impact 5 · Feasibility 5 · **Priority 25** · `[NOW]` · Depends on: —
- **Problem:** ExperimentMetric rows (apps/api/researchos/experiments/models.py) render only in the Recharts
  dashboard; every number in a paper is hand-typed into a DocumentFile and silently rots.
  LATEX_PIPELINE.md section 8 promises experiment-to-paper sync but zero code implements it — there is no
  table, endpoint, or UI linking a run metric to a LaTeX token.
- **Proposal:** A result_bindings table maps a macro name (\ResBestAcc) to (experiment, run-or-latest, metric,
  aggregation, format). A Celery hook regenerates a results/anchors.tex DocumentFile full of \newcommand
  definitions whenever a bound run completes; the paper references macros instead of literals, so numbers
  update themselves and carry provenance.
- **Algorithm sketch:**
  1) Table result_bindings(id, latex_project_id FK, macro_name unique-per-project matching [A-Za-z]+, experiment_id, run_id nullable — null means "latest COMPLETED run of experiment", metric_name, aggregation enum{final,best,min,max,mean}, format_spec e.g. '{:.2f}', scale float default 1.0, last_value float, last_run_id, created_by).
  2) API: POST/GET/DELETE `/projects/{pid}/latex-projects/{lid}/result-bindings`; POST `.../regenerate`.
  3) Regeneration task (Celery, triggered on ExperimentRunStatus→COMPLETED and by explicit POST): resolve source run per binding, reduce metric series with the exact logic already in experiment_agent._summarize (best = min if 'loss' in name else max), render `'\newcommand{\ResBestAcc}{92.41}'` lines, upsert DocumentFile at path results/anchors.tex (version+1, updated_by=system).
  4) Paper editor: "Insert result" popover lists bindings, inserts macro at cursor; extend the mock compiler to substitute known macros so the text preview shows real numbers.
  5) Each regeneration records run→binding→document provenance edges (see WS8-2).

### WS3-2. Run telemetry contract: NDJSON ingest API, run-scoped tokens, and a stdlib client shim
- Source: SYS lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: —
- **Problem:** Every ExperimentMetric/ExperimentLog row today comes from the demo seed or hand-called CRUD
  endpoints — a real training script has no way to feed a run, so the entire experiment→paper pipeline runs on
  fiction. EXPERIMENT_SYSTEM.md section 5 lists JSONL ingestion as MVP scope; no ingest endpoint exists in
  experiments/router.py.
- **Proposal:** Define one canonical NDJSON event contract (metric/log/artifact/status lines), a batch ingest
  endpoint authenticated by run-scoped bearer tokens (so scripts never hold user cookies), and a single-file
  stdlib-only Python client so any training loop feeds live charts, anchors, and figures with three lines of
  code.
- **Algorithm sketch:**
  1) Contract, one JSON object per line: `{"t":"metric","name":"loss","step":10,"value":0.5}` | `{"t":"log","level":"info","msg":"..."}` | `{"t":"artifact","name":"cm.png","size":..}` | `{"t":"status","status":"completed"}`.
  2) `POST /experiment-runs/{id}/token` → opaque token stored in Redis {run_id, project_id, TTL 7d}; revoke on run finalize.
  3) `POST /ingest/runs/{run_id}` accepts NDJSON body (cap 1000 lines/request), validates each line against a discriminated-union schema, bulk-inserts metrics/logs with monotone seq, applies status transitions through the existing lifecycle enum, publishes WS events for live Recharts updates.
  4) Client researchos_client.py (~60 lines, urllib only): `RunLogger(base_url, token).metric(name, value, step)`; buffers, flushes every 2s or 100 events, retries with backoff; plus `python -m researchos_client tail metrics.jsonl` to ship an existing file.
  5) artifact lines respond with a presigned MinIO PUT URL so scripts push bytes directly; ingest registers the ExperimentArtifact row on upload confirmation.

### WS3-3. Staleness sentinel: detect when a new run supersedes paper numbers
- Source: SYS lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: WS3-1.
- **Problem:** Nothing in the codebase knows a paper asset is out of date. LatexCompileJob
  (documents/models.py) transforms text with no awareness of experiments; if run 47 beats run 32, the paper
  keeps run 32's numbers forever with no warning anywhere.
- **Proposal:** A staleness service recomputes, on every run completion, whether each result binding and figure
  binding still reflects the newest completed run; stale anchors get Monaco gutter badges, compile-log WARN
  lines, and a one-click "rebind to latest and regenerate" action.
- **Algorithm sketch:**
  1) Staleness rule: binding is stale iff (a) run_id is pinned and a newer COMPLETED run exists in the same experiment, or (b) re-resolving the binding yields value != last_value.
  2) Hook: the same run-completion Celery task from WS3-1 recomputes flags, sets result_bindings.stale / figure_bindings.stale, and publishes a paper.staleness event on the existing Redis pub/sub → WebSocket channel (websocket/envelopes.py).
  3) API: `GET /latex-projects/{lid}/staleness` → `[{macro_name, bound_run_id, latest_run_id, bound_value, latest_value, delta_pct}]`.
  4) Frontend: regex-scan open document content for `\Res*` macro names, mark matching lines with a yellow gutter decoration; banner above preview lists stale items with "Update all" → POST rebind+regenerate.
  5) Mock (later real) compile appends `'WARN stale: \ResBestAcc bound to run 32, run 47 is newer (+1.3%)'` lines to LatexCompileJob.log so staleness surfaces even in CI-style compiles.

### WS3-4. Figure worker: matplotlib renders paper figures from run metrics into real object storage
- Source: SYS lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: —
- **Problem:** Papers cannot contain figures at all: DocumentFile stores only Text content,
  ExperimentArtifact.uri is a dead string, and common/storage.py is merely a MinIO health probe — no bytes are
  ever written. Dashboard charts are client-side Recharts that never become paper assets.
- **Proposal:** A figures.render Celery worker plots ExperimentMetric series with matplotlib into PDF+PNG,
  writes bytes to MinIO (implementing the deferred storage abstraction), registers them in a new
  document_assets table, and inserts a \begin{figure} block with a machine-readable provenance comment.
  Re-render is one click when a newer run lands.
- **Algorithm sketch:**
  1) FigureSpec JSON: `{kind: line|bar|scatter, series: [{run_id, metric_name, label, smoothing_window?}], x: 'step', style_preset_slug, layout: single|double_column, caption_seed}`.
  2) Tables: figure_bindings(id, latex_project_id, name, spec_json JSONB, asset_path 'figures/lr-ablation.pdf', source_run_ids uuid[], style_slug, style_version, last_rendered_at, stale bool); document_assets(id, latex_project_id, path unique-per-project, content_type, size_bytes, sha256, storage_key).
  3) `POST /latex-projects/{lid}/figures {spec}` → Celery figures.render: SELECT metrics ordered by step, mpl.rc_context(preset rcParams), savefig PDF+PNG to bytes, minio put_object at `paper-assets/{project_id}/{lid}/{name}.{ext}`, upsert document_assets, WS event figure.rendered.
  4) `GET /latex-projects/{lid}/assets/{path}` streams from MinIO so the preview pane shows `<img>` thumbnails.
  5) Insert action writes: `'% researchos:figure {binding_id}'` + `\begin{figure}\includegraphics{figures/lr-ablation}\caption{...}\label{fig:...}`. The comment is the anchor the staleness scanner and re-render target.
  6) Run completion in a bound experiment flips stale; "Re-render from latest" rebuilds spec against the newest run.

### WS3-5. Run-comparison LaTeX table generator + paper-asset review inbox
- Source: SYS lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: WS3-1.
- **Problem:** EXPERIMENT_SYSTEM.md section 7 promises "Export to LaTeX table" and LATEX_PIPELINE.md section 8
  promises reviewed asset candidates; neither exists. The dashboard shows runs side by side but produces no
  paper text, and the writing assistant (latex_agent.py) has no tools and no access to run data.
- **Proposal:** A deterministic booktabs table generator over selected runs (numbers computed server-side,
  never by the LLM; caption drafted by LatexAgent) feeding a paper_asset_candidates inbox in the paper
  workspace. Accepting a candidate inserts anchored LaTeX at the cursor or a section marker, embedding
  result-anchor macros so tables inherit staleness detection.
- **Algorithm sketch:**
  1) `POST /projects/{pid}/paper-assets/table {run_ids[], metric_names[], higher_is_better: {metric: bool}, bold_best: true}` → generator pulls final/best per the _summarize reduction, emits `\begin{table}[t]\begin{tabular}` with `\textbf{}` on per-column winners; caption_seed passed to LatexAgent for an LLM caption (numbers stripped from its context to prevent invention).
  2) Table paper_asset_candidates(id, project_id, latex_project_id, kind: table|figure|snippet, latex_source Text, caption Text, source_run_ids uuid[], status pending|accepted|dismissed, created_from manual|on_run_completed).
  3) Auto mode: run-completion hook creates a one-row summary candidate for experiments that have active bindings.
  4) UI: "Assets inbox" tab in the paper workspace right pane; each card shows mock-compiled preview + source-run chips; Accept inserts at cursor or at a `'% researchos:section results'` marker.
  5) Where a result binding covers a cell, the generator emits `\ResMacro` instead of the literal; acceptance writes run→candidate→document provenance edges.

### WS3-6. Figure style presets as skills + per-user style setting + one-click chart-to-paper (merged)
- **Merged from:** SYS "Figure style presets as skills with a per-user style setting" + UX "Figure style
  presets in Settings + one-click chart-to-paper insertion".
- Impact 3 · Feasibility 4 · **Priority 12** · `[NOW]` · Depends on: WS3-4 (for the canonical server-side
  render path; the client-side Recharts insertion is a standalone quick win).
- **Problem:** SKILLS_SYSTEM.md lists "Figure skill" as a type, but SkillManifest (skills/manifest.py) has no
  style concept, Settings has no figure preference (settings/page.tsx contains only Language and LLM-config
  cards), MetricsChart.tsx hardcodes Recharts colors, and experiments have zero paper linkage — wishlist 7's
  "selectable figure styles" has neither a settings surface nor an insertion path. The marketplace machinery
  (Skill/SkillVersion/SkillInstallation, version pinning) exists and is unused for this.
- **Proposal:** Extend the manifest with a declarative style_json (allowlisted matplotlib rcParams + palette),
  ship 4 first-party presets via skills/seed.py, add a per-user figure_style setting with a rendered preview
  gallery in Settings, apply the preset both to the Recharts dashboard (mapped props) and to the matplotlib
  figure worker (rc_context), and offer "Insert into paper" on any run's metric chart. Skill version bumps mark
  dependent figures stale, giving "auto-download latest beautiful figure skills" semantics through the
  existing install/pin/update flow.
- **Algorithm sketch (skills + settings + worker path):**
  1) Manifest change: new SkillModule.FIGURE_STYLE and field style_json validated against an rcParams allowlist (axes.prop_cycle colors, font.size/family, figure.dpi, grid.*, spines flags, legend.*) — arbitrary keys rejected, keeping the "no code in manifests" rule.
  2) seed.py adds presets: neurips-clean, ieee-mono, nature-compact, vibrant-slides (category='figure-style'). (UX-lens naming variants: Conference serif, Nature-ish, Minimal grayscale, Colorblind-safe — pick one set of 4.)
  3) Settings: user_settings.figure_style_slug plus optional per-latex-project override; resolution order project > user > default. Settings shows a Figures card: preset gallery, each tile a live preview; radio select applies immediately (persist via `PUT /projects/{id}/settings {figure_style_id}` following the llm-config router pattern).
  4) figures.render resolves the pinned SkillVersion of the slug, applies rc_context(style_json), and stamps style_slug+version into figure_bindings.
  5) Gallery: figures.render_style_preview task renders one fixture dataset per installed style, cached in MinIO keyed (slug, version); Settings shows the strip, click-to-select.
  6) Update flow: when a newer SkillVersion is installed, figures whose stamped version differs flip stale → "Re-render in new style" banner in the paper workspace.
- **Algorithm sketch (dashboard + client-side quick-win insertion):**
  1) MetricsChart refactor: accept style prop mapped to Recharts props (Line stroke/strokeWidth from palette, CartesianGrid on/off, tick font); dashboard reads the project preset via query.
  2) Insert-into-paper in RunDetail: grab the rendered SVG node (ref.outerHTML), inline computed font styles, rasterize to PNG via canvas (drawImage of an SVG blob) at 2x, save through documents save_file as `figures/{runName}-{metric}.png`; generate snippet `'\begin{figure}[t]\centering\includegraphics[width=\linewidth]{figures/...}\caption{{metric} across training steps for {runName} (best {bestValue} at step {bestStep}).}\label{fig:{slug}}\end{figure}'`; append to main.tex (or clipboard fallback) + toast linking to the Paper workspace. Caption fields come from run metadata already shown in RunDetail.

---

## WS4 — Overleaf-Grade Writing
**Owner scope:** wishlist 8 (write yourself OR AI floating assistant) plus the write-side of wishlist 2.
One engineer owns the LaTeX editor, the selection assistant, real compile, and library→prose synthesis.
**Suggested order:** Editor core → Floating assistant → Real compile → Related-work weaver.

### WS4-1. Overleaf-grade LaTeX editor core: syntax, snippets, cite/ref completion, outline, multi-file, autosave
- Source: UX lens. Impact 4 · Feasibility 5 · **Priority 20** · `[NOW]` · Depends on: —
- **Problem:** PaperWorkspace.tsx hardcodes a single main.tex and mounts Monaco with language="plaintext" — no
  LaTeX highlighting at all — plus a manual Save button and no outline or citation support. The documents
  backend already supports list_files/get_file/save_file for arbitrary paths (documents/service.py), but the UI
  never calls list_files.
- **Proposal:** Turn the center pane into a real LaTeX editor: Monarch LaTeX grammar,
  environment/citation/ref completions, a clickable document outline, multi-file tabs (main.tex,
  sections/*.tex, refs.bib), and debounced autosave — all against existing APIs.
- **Algorithm sketch:**
  1) monaco.tsx: `monaco.languages.register('latex')` + Monarch tokenizer (commands `\\[a-zA-Z]+`, math `$..$` and `\[..\]`, comments `%`, environment names, braces); language config for bracket pairs and auto-closing `$`.
  2) CompletionItemProvider: (a) snippet completions for `\begin{$1}…\end{$1}`, `\section`, `\cite`, `\ref`, figure/table/equation templates; (b) on trigger character '{' after \cite: fetch refs.bib via documents get_file, regex `@\w+\{([^,]+),` → keys with entry title as detail; (c) after \ref{: scan all project .tex buffers for `\label{([^}]+)}`.
  3) Outline panel above PaperAssistant: regex `\(sub)*section{...}` over the active buffer → tree `[{level, title, line}]`; click → editor.revealLineInCenter + setPosition.
  4) Multi-file: call list_files, render EditorPane-style tab bar with per-file zustand buffers and dirty dots; refs.bib gets a plain bibtex grammar.
  5) Autosave: 1.5s debounce → save_file, status chip cycling saving…/saved + Ctrl+S force; optional compile-on-save toggle stored in localStorage.

### WS4-2. Floating selection assistant with tracked changes (accept/reject AI edits in the paper)
- Source: UX lens. Impact 5 · Feasibility 4 · **Priority 20** · `[NOW]` · Depends on: WS4-1.
- **Problem:** PaperAssistant.tsx is a detached left-pane ask box whose output renders into a `<pre>` and can
  never touch the editor — the user must manually copy text. There is no selection-based action, no "continue
  writing", and no way to see what the AI wants to change before it changes it, violating UI_UX.md section 7:
  "AI edits should remain inspectable and reversible".
- **Proposal:** Overleaf/Cursor-style floating toolbar on text selection inside the LaTeX editor — Rewrite
  academically, Fix grammar, Condense, Expand, Continue at cursor, custom instruction — whose result appears as
  a tracked change (original struck through, replacement in green) with per-suggestion Accept/Reject, each
  linked to its agent run.
- **Algorithm sketch:**
  1) Selection UI: onDidChangeCursorSelection → non-empty selection shows a Monaco content widget toolbar anchored above the selection; "Continue" variant appears at cursor when selection is empty.
  2) Request: createAgentRun `{agent_type:'latex', message: JSON.stringify({action, selection_text, before_context: prev 40 lines, after_context: next 20 lines, file, range})}`; extend latex_agent.py with response_schema `{replacement:string, rationale:string}` (the structured-output mechanism already exists — coding_agent.py uses response_schema today).
  3) Tracked change: on completion create EditSuggestion `{id, file, range, original, replacement, rationale, agent_run_id, status:'proposed'}` in a zustand store; render via deltaDecorations (strikethrough red on original) + an IViewZone beneath showing the replacement text, rationale line, and Accept/Reject/Retry buttons.
  4) Accept → `editor.executeEdits([{range, text: replacement}])` + shift ranges of remaining suggestions by line delta + autosave; Reject → remove decorations.
  5) A "Suggestions" list in the left pane shows pending + resolved suggestions with links to their agent runs for traceability.

### WS4-3. Real PDF compile preview with error-to-line mapping
- Source: UX lens (compile engine also appears as the `kind=latex` path of WS6-1's sandboxed runner — tectonic
  in the Celery worker is the near-term engine; the runner's latexmk path is the long-term home).
- Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: WS4-1.
- **Problem:** Compile is a mock pure-Python text transform (MVP_STATUS: "Mock compiler — no shell, no PDF")
  and PreviewPanel.tsx renders the result as a plain `<pre>` text dump; error_summary is an unstructured blob
  with no editor integration, so the paper workspace cannot deliver its core Overleaf promise.
- **Proposal:** Ship real compilation via the tectonic single-binary engine in the Celery worker, render actual
  PDF pages with pdf.js in the right pane, and parse the LaTeX log into per-line editor markers with
  click-to-jump errors.
- **Algorithm sketch:**
  1) Worker Dockerfile: add tectonic (~50MB static binary, downloaded at build time — no accounts); compile task: write all latex-project files to a tmpdir, run `tectonic --keep-logs main.tex` with 60s timeout and no shell-escape, capture log + PDF bytes; store PDF under the project workspace artifacts dir; keep the mock provider behind an env flag as fallback so existing tests pass.
  2) Log parser: state machine tracking file stack from `'(./sections/x.tex'` tokens; error records from `'! <message>'` followed by `'l.<line>'` → `[{file, line, message, severity}]`; warnings from `'LaTeX Warning:'`.
  3) API: compile job response gains `{pdf_url, log, errors[]}`; GET pdf endpoint streams application/pdf.
  4) PreviewPanel: tabs PDF | Log; PDF tab uses bundled pdfjs-dist canvas rendering with page prev/next + zoom + fit-width, remembers scroll position across recompiles.
  5) Editor: monaco.setModelMarkers per file from errors[] (red squiggles + hover message); error list rows click → open that file tab and revealLineInCenter.
  6) Compile button shows spinner + last-success timestamp chip.
  7) Migration path: when WS6-1 lands, `kind=latex` jobs run `latexmk -pdf -interaction=nonstopmode -no-shell-escape` in the network-isolated runner; tectonic-in-worker becomes the fallback, mock stays for CI.

### WS4-4. Related-work weaver: citation-grounded synthesis from library sections into the paper workspace
- Source: ALGO lens. Impact 4 · Feasibility 2 · **Priority 8** · Transformative-bet · Depends on: WS1-3, WS1-4, WS2-2.
- **Problem:** ResearchAgent produces a chat answer with citation keys, but nothing turns the library into
  paper-ready prose: the LaTeX workspace (latex_agent.py, writing assistant) and the research library are
  disconnected, and abstract-only context makes any related-work draft shallow. This is the algorithmic bridge
  between wishlist items 2 and 8 that neither side covers.
- **Proposal:** A RELATED_WORK agent mode that clusters the project library by embedding similarity into
  themes, drafts one paragraph per theme grounded in ingested intro/method sections (not just abstracts), emits
  \cite{key} commands wired to an auto-generated references.bib built from real Paper metadata, and delivers
  the result as a reviewable patch to the LaTeX workspace — reusing the coding-agent patch flow for prose.
- **Algorithm sketch:**
  1) Theme clustering (deterministic, no LLM): fetch library embeddings from pgvector; agglomerative clustering with cosine threshold 0.35, min cluster size 2, singletons merged into 'other'; label each cluster by top-TF-IDF terms across member titles.
  2) BibTeX generation: for each Paper, key = firstauthorYYYYfirstword; entry from authors_json/title/venue/published_at/url — pure function, unit-testable; write references.bib via a patch file.
  3) Drafting loop: one LLM call per cluster with context = member papers' abstract + intro-section extracts (from paper_sections) + the project's own idea descriptions for contrast; hard rule mirroring citations.py: every sentence mentioning a work must contain \cite{key} where key ∈ generated bib — finalize validates by regex and drops/flags violating sentences.
  4) Assembly: paragraphs ordered by cluster size desc + a topic sentence transition generated in one final pass; output = two-file patch {main.tex: insert into \section{Related Work} via search/replace hunk, references.bib: create/merge}.
  5) Merge policy for existing bib: parse existing keys, never duplicate, suffix collisions with 'a/b'.
  6) UI: "Draft related work from library" button in the paper workspace; result appears in the standard patch-review diff — traceability for AI prose, exactly what the roadmap guardrail ("traceability must remain visible in all AI-generated paper content") demands.
  7) Prose quality per theme needs prompt iteration with a real LLM, hence the feasibility rating.

---

## WS5 — Idea Generation & Validation
**Owner scope:** wishlist 3. Both ideas are quality-iteration-heavy: build the plumbing now, budget weeks of
smoke-testing against real libraries and real LLM keys. Pairs with WS6 for actual smoke runs.

### WS5-1. Gap-matrix idea generation: typed claims extraction + uncovered-cell mining
- Source: ALGO lens. Impact 5 · Feasibility 2 · **Priority 10** · Transformative-bet · Depends on: WS1-3, WS1-4.
- **Problem:** IdeaService.create (research/service.py) only stores ideas the user types in by hand;
  Idea.novelty_score exists in the model but nothing ever writes it. Wishlist item 3 wants literature-driven
  idea generation, and today there is no generation path at all.
- **Proposal:** An IDEATE agent that first extracts a typed claims matrix from N library papers
  (problem × method × dataset × limitation rows), then mines the matrix deterministically for gaps
  (method-problem cells with no covering paper, limitations no follow-up addresses, cross-domain transfers),
  and only then asks the LLM to turn each mined gap into a concrete Idea row — grounding generation in
  structure instead of vibes.
- **Algorithm sketch:**
  1) New table paper_claims: `{paper_id FK, problem str, method str, datasets list, key_result str, stated_limitations list, domain str}` — filled by a per-paper extraction LLM call with a strict response_schema, run as a Celery task over library papers (input = abstract + intro/conclusion sections when ingested).
  2) Deterministic gap mining (pure Python, no LLM): build sets P (problems), M (methods), coverage = {(p,m) with a paper}; candidate gaps = {(p,m) not in coverage where p and m each appear >=2 times}; limitation gaps = limitations with no later paper whose problem matches (embedding cosine > 0.7 using the pgvector embeddings); transfer candidates = (method from domain A, problem from domain B) where domains differ. Rank candidates by support count.
  3) IDEATE agent input: top-10 mined candidates serialized as JSON; response_schema = `{ideas: [{title, description, hypothesis, gap_type: 'coverage'|'limitation'|'transfer', supporting_paper_keys: [source:external_id]}]}`; supporting keys validated against the whitelist like citations.
  4) finalize: persist each as Idea (status=DRAFT) + link supporting papers in metadata; auto-enqueue the existing CriticAgent on each new idea so every generated idea arrives with a critique attached.
  5) UI: "Generate ideas from library" button on the Ideas page; each card shows gap type + supporting papers + critic verdict.
  6) Quality depends on extraction prompt fidelity and gap thresholds — needs repeated smoke-runs against a real library and real LLM.

### WS5-2. Novelty gauntlet: iterative propose → search → score → revise loop for ideas
- Source: ALGO lens. Impact 4 · Feasibility 2 · **Priority 8** · Transformative-bet · Depends on: WS1-2, WS1-4.
- **Problem:** Idea.novelty_score is a dead column and CriticAgent critiques in one shot from whatever the
  whitelist happens to contain. Nothing checks a candidate idea against literature the project hasn't imported
  yet, and there is no revision loop — exactly the AI-Scientist-style iteration wishlist item 3 asks for.
- **Proposal:** A multi-round Celery pipeline: for a given idea, generate 3 targeted search queries, run them
  through the (federated) paper.search, embed the top hits, score novelty as distance-to-nearest-neighbor, feed
  the closest "threat papers" back to the LLM to either differentiate or revise the idea, and repeat up to 3
  rounds — persisting every round so the user can watch the idea harden.
- **Algorithm sketch:**
  1) New table idea_novelty_rounds: `{idea_id, round int, queries list, threat_papers jsonb [{key, title, similarity}], novelty_score float, revision_diff text, verdict enum('novel','crowded','revised')}`.
  2) Round algorithm: (a) LLM call: given idea title+description+hypothesis, emit 3 search queries targeting the closest prior work (schema-constrained); (b) run each through paper.search limit=10 (federation makes this meaningful beyond arXiv); (c) embed idea text and all hits; `novelty_score = 1 - max cosine(idea, hit)`; (d) if score < 0.25: verdict 'crowded' — LLM receives the top-3 threats' abstracts and must either output a differentiation statement or a revised description (schema: `{action: 'differentiate'|'revise', text}`); revision updates the Idea row and triggers round+1; (e) if score >= 0.25 or round == 3: stop, write Idea.novelty_score, append threat papers to the idea's citations.
  3) Runs as a chained Celery task reusing the AgentRun/event machinery so each round streams to the UI over the existing WebSocket channel.
  4) UI: novelty timeline on the idea detail page — rounds, score sparkline, threat-paper chips (click to import).
  5) Thresholds (0.25) and query-generation prompts are the iteration surface; every round is persisted, so tuning has ground truth to compare against.

---

## WS6 — Execution & Remote Runtimes
**Owner scope:** the "real execution" substrate that wishlist 3 (smoke-testing ideas) and real compile need.
Infra-heavy; one engineer owns the runner container, job spool protocol, and SSH runtime.

### WS6-1. Sandboxed execution runner: real terminal jobs, real smoke runs, real LaTeX PDFs
- Source: SYS lens. Impact 5 · Feasibility 3 · **Priority 15** · Transformative-bet (scaffold `[NOW]`) ·
  Depends on: WS2-3 (git-archive snapshots), WS3-2 (telemetry parser).
- **Problem:** The terminal panel is a UI shell with no execution, LaTeX compile is a Python text transform,
  and no run can actually execute code anywhere in the stack — so idea validation by smoke-testing (wishlist 3)
  and real compile are both impossible today.
- **Proposal:** A dedicated runner container in docker-compose with network_mode:none and a shared job-spool
  volume: the API writes a job dir (spec + git-archive tarball of an exact commit), the runner executes under
  rlimits and streams line-buffered output back through the spool, and an API-side collector pipes lines to the
  existing Redis pub/sub WebSocket channel, ingests emitted researchos.jsonl as run metrics, and uploads
  declared outputs to MinIO. The same runner executes latexmk for real PDF compiles.
- **Algorithm sketch:**
  1) compose service runner: image python+texlive-basic, network_mode: none, read-only rootfs except /work and /spool, pids/mem/cpu limits; supervisor loop watches /spool/incoming.
  2) Job spec job.json: `{job_id, kind: command|latex, commit_sha, argv[], timeout_s, mem_mb, expected_outputs: [globs]}`; workspace snapshot produced by git-archive of commit_sha (exact provenance, no dirty state).
  3) Runner: extract tarball to /work/{job_id}, exec argv with setsid+rlimit+timeout, write stdout/stderr as seq-numbered NDJSON to /spool/outgoing/{job_id}/out.ndjson, then result.json `{exit_code, duration}`, copy expected_outputs into the job dir.
  4) API-side Celery collector: tails out.ndjson, republishes to Redis channel exec:{job_id} (frontend terminal panel subscribes via existing WS envelopes); on result.json, parse any researchos.jsonl in outputs through the telemetry-contract parser into an ExperimentRun (metrics, logs, status), upload outputs to MinIO as ExperimentArtifacts.
  5) kind=latex runs `latexmk -pdf -interaction=nonstopmode -no-shell-escape`; PDF stored as a document asset, log parsed into LatexCompileJob.log — the mock compiler becomes the offline fallback.
  6) Terminal panel v1: xterm.js output-only, command palette entries "Run <script>", "Compile paper"; every job records its commit_sha for provenance.

### WS6-2. SSH smoke-test runtime: approval-gated remote execution with live metric tailing
- Source: SYS lens. Impact 4 · Feasibility 2 (needs-external-services) · **Priority 8** · Transformative-bet ·
  Depends on: WS3-2.
- **Problem:** SSH_RUNTIME.md fully specifies profiles, approval gates, and metric collection, but MVP_STATUS
  confirms only an interface exists — no connection code, no credential storage, no remote runs. The owner
  explicitly wants idea smoke-tests on real GPU servers.
- **Proposal:** Implement the minimal documented path: runtime-profile CRUD with Fernet-encrypted private keys,
  an asyncssh execution task in a dedicated Celery queue, live stdout streaming to the existing WebSocket,
  periodic SFTP tailing of metrics.jsonl into ExperimentMetric via the telemetry parser, and artifact pull-back
  to MinIO — every launch behind the approval modal the doc already specifies.
- **Algorithm sketch:**
  1) Table runtime_profiles per SSH_RUNTIME.md section 3; private key Fernet-encrypted with a key derived from settings secret; API never returns key material.
  2) `POST /experiment-runs/{id}/launch-remote {profile_id, workdir, command, env}` → approval record; UI modal shows host, cwd, command, env (secrets excluded) per doc section 5; approve → enqueue ssh.execute on queue 'remote'.
  3) ssh.execute: asyncssh.connect(timeout=10, known_hosts TOFU pinned on profile); create_process('cd {workdir} && {command}'); stream stdout lines → Redis pub/sub exec:{run_id} + batched ExperimentLog inserts; every 5s SFTP-read the tail offset of {workdir}/metrics.jsonl and feed the run-telemetry parser (dedupe by byte offset stored in run config_json).
  4) On exit: SFTP-glob declared artifact patterns (per-file size cap), stream to MinIO, register ExperimentArtifacts; map exit code → COMPLETED/FAILED; classify failures per doc section 8 into run.config_json.failure_class, always preserving logs.
  5) Cancellation: existing agents/cancellation.py pattern — Redis flag polled between reads, then process.terminate().
  6) Run stores git_commit + command + profile name, so remote results join the provenance graph like sandbox runs.

---

## WS7 — Design System & IDE Polish
**Owner scope:** wishlist 4 (prettier IDE) plus product coherence. Frontend-leaning engineer; all four ideas
are independent and shippable this session.

### WS7-1. Semantic design tokens + dark mode + theme-aware Monaco/Recharts
- Source: UX lens. Impact 4 · Feasibility 5 · **Priority 20** · `[NOW]` · Depends on: —
- **Problem:** globals.css declares --color-bg/surface/border/text/accent variables that no component consumes;
  all ~60 tsx files hardcode Tailwind neutral-*/amber-*/emerald-* classes, and the stylesheet actively forces
  light mode (@media prefers-color-scheme: dark → color-scheme: light). There is no theme toggle, and Monaco +
  Recharts render light-only.
- **Proposal:** Activate the dead tokens as a real semantic layer (bg, surface, surface-2, border, text,
  text-muted, accent, success, warn, danger), sweep the codebase onto them, and ship a light/dark/system toggle
  in the TopBar and Settings that also themes Monaco and charts.
- **Algorithm sketch:**
  1) tailwind.config: `colors.{bg,surface,surface2,border,text,muted,accent,accentFg,success,warn,danger} = 'rgb(var(--color-x) / <alpha-value>)'`.
  2) globals.css: token values under :root (light) and :root[data-theme="dark"]; prefers-color-scheme respected only when stored preference is 'system'.
  3) Mechanical codemod sweep with a mapping table: bg-neutral-50→bg-bg, bg-white→bg-surface, border-neutral-200→border-border, text-neutral-900→text-text, text-neutral-400/500→text-muted, bg-neutral-900 (primary buttons)→bg-accent, amber pills→warn, emerald pills→success; manual pass on the 6 status-pill maps (PatchReviewPanel.statusStyle etc.).
  4) ThemeProvider in app/providers.tsx: useTheme() {theme, setTheme}, persisted in localStorage 'ros-theme', stamps data-theme on `<html>` pre-hydration via inline script to avoid flash.
  5) Monaco wrapper (lib/ide/monaco.tsx): `theme={dark?'vs-dark':'vs'}`; MetricsChart reads stroke/grid colors from getComputedStyle CSS vars.
  6) Settings gains an Appearance card (3 radio tiles with mini previews); TopBar gets a sun/moon toggle.

### WS7-2. Command palette (Ctrl+K) + keyboard-first navigation
- Source: UX lens. Impact 4 · Feasibility 5 · **Priority 20** · `[NOW]` · Depends on: —
- **Problem:** A grep across apps/web for cmdk/keydown/metaKey/ctrlKey returns zero hits — the product has no
  command palette, no shortcuts, not even Ctrl+S in the editors; every action is mouse-only through SideRail
  and buttons, which undercuts the "professional research cockpit" positioning in docs/UI_UX.md.
- **Proposal:** A client-side command registry + Ctrl/Cmd+K palette that fuzzy-searches navigation, actions,
  workspace files, and library papers, plus a thin global shortcut layer (Ctrl+S save, Ctrl+Enter send,
  g-then-letter module hops) with a ? cheatsheet dialog.
- **Algorithm sketch:**
  1) Registry: Command = `{id, title, section:'navigate'|'action'|'file'|'paper', keywords:string[], shortcut?:string, run(ctx:{router, projectId, queryClient})}`. Static commands: go to Overview/Research/IDE/Experiments/Paper/Skills/Settings, toggle theme, compile paper, new coding request. Dynamic providers pull from React Query cache: workspace tree files (['workspace-tree']) → open-in-IDE commands; library papers (['papers']) → open reading view; recent agent runs.
  2) Palette: modal listbox, subsequence fuzzy scorer (no new dependency: score = matched-char density + word-boundary bonus), grouped by section, top 8 per group, MRU boost from localStorage.
  3) Shortcut layer mounted in (workspace)/layout.tsx: single keydown listener with a scope stack; suppressed when target is input/textarea/Monaco unless modifier held; bindings map `{'mod+k': openPalette, 'mod+s': saveActive (editor propose-patch or paper save), 'mod+enter': submitActiveChat, 'g i|r|e|p|s': navigate}`.
  4) '?' opens a shortcuts cheatsheet rendered from the registry so docs never drift.
  5) Buttons gain `<kbd>` hints in tooltips.

### WS7-3. Unified agent run inspector: every AI action explainable post-hoc
- Source: UX lens. Impact 3 · Feasibility 5 · **Priority 15** · `[NOW]` · Depends on: —
- **Problem:** The backend persists agent_run_events and tool_calls for every run (events.py, tools.py
  ToolBroker), but the UI throws this away: persisted research runs render only output text plus raw
  'arxiv:2401.12345' citation keys (ResearchChat.tsx), and coding/latex/experiment agents surface no trace at
  all — breaking PRODUCT.md principle 1, "Trace every AI action to source context, tool calls, and project
  artifacts".
- **Proposal:** A RunInspector drawer (the "right tray" UI_UX.md section 2 already calls for) openable from any
  chat bubble, patch card, or analysis panel: full event timeline, expandable tool calls with
  arguments/results, token usage and duration, linked patch/citations resolved to human-readable titles, and a
  re-run button.
- **Algorithm sketch:**
  1) API: `GET /projects/{id}/agent-runs/{runId}/detail` → `{run, events:[{seq, type, payload, ts}], tool_calls:[{seq, tool_name, arguments_json, result_summary, status, duration_ms}], patch?:{id, summary, status}, usage}` — repositories already exist (AgentRunEventRepository, ToolCallRepository); one new router method joins them.
  2) RunInspector drawer component slides over the right edge: header (agent type icon, status, started/duration, model name from usage), vertical timeline rendering events in seq order — started → tool call rows (collapsed: name + result_summary; expanded: pretty-printed args and result JSON) → completed with usage footer (prompt/completion tokens).
  3) Citations section resolves source:external_id → {title, url} from the completed event's citations payload (already persisted by EventEmitter.completed) and renders proper source chips instead of raw keys; same resolution back-ported into ResearchChat persisted messages.
  4) Entry points: an inspect icon on every chat bubble (research/coding/paper), "view run" on PatchCards, and on the experiments AnalysisPanel.
  5) Footer "Re-run with same input" calls createAgentRun with run.input_json.

### WS7-4. Golden-path onboarding checklist + actionable empty states
- Source: UX lens. Impact 3 · Feasibility 5 · **Priority 15** · `[NOW]` · Depends on: —
- **Problem:** Empty states today are passive one-liners — "No papers yet." (PaperLibrary), "No patches yet."
  (PatchReviewPanel), an emoji + single button (PaperWorkspace) — despite docs/UI_UX.md section 10 explicitly
  requiring action-driven empty states; a new user landing in a fresh project has no guided path through the
  research loop the MVP is supposed to prove.
- **Proposal:** A "Get your research loop running" checklist card on Project Overview whose six steps derive
  completion from real data (no new tables), plus a shared EmptyState component with primary CTAs deep-linking
  into the exact next action across every module.
- **Algorithm sketch:**
  1) useOnboardingProgress(projectId) hook computes steps entirely from existing queries: savedPaper (library total>0), firstIdea (ideas>0), askedAgent (agent runs>0), experimentCreated, paperStarted (latex projects>0), skillInstalled; returns `{steps:[{id, label, done, href, cta}], percent}`.
  2) OnboardingChecklist card on Overview: progress ring + 6 rows with checkmarks; each row's CTA router-pushes with a focus hint query param (e.g. /research?focus=search) that the target page reads to auto-focus the relevant input; card auto-collapses at 100% and is dismissable (localStorage).
  3) `<EmptyState icon title body actions[]>` component replacing all bare "No X yet" strings; each instance offers a primary action (Search papers / Ask the agent / Create experiment / Start paper) and, where safe, a one-click starter (e.g. import a canonical arXiv id into the library via the existing import endpoint).
  4) i18n keys added for zh-CN/en-US per the existing lib/i18n pattern.

---

## WS8 — Skills, Provenance & Orchestration
**Owner scope:** the "one agent fabric" layer — making skills real at runtime, wiring the provenance moat, and
eventually chaining agents into pipelines. Touches every other workstream's outputs.
**Suggested order:** Skill injection → Provenance graph (after WS3-1 + WS2-3 land) → Pipelines.

### WS8-1. Skill runtime injection with a tool-permission broker and per-run audit
- Source: SYS lens. Impact 4 · Feasibility 4 · **Priority 16** · `[NOW]` · Depends on: —
- **Problem:** Skills can be installed, enabled, and version-pinned (skills/models.py), and manifests already
  carry prompt_template, workflow, and tool_permissions (skills/manifest.py) — but AgentRuntime.run
  (agents/runtime/runtime.py) never reads any of it. README states skills "are never injected into agent
  runtime"; the marketplace is decorative.
- **Proposal:** An injection stage in AgentRuntime: enabled project skills matching the agent type contribute
  prompt fragments and workflow hints to the system message, and their tool_permissions widen the agent's tool
  set only through a broker that intersects manifest grants, the platform ALLOWED_TOOLS allowlist, and project
  policy. Every grant and tool call is attributed to its skill in the run event stream.
- **Algorithm sketch:**
  1) SkillContextBuilder: SELECT SkillInstallation JOIN pinned SkillVersion WHERE project_id=? AND enabled AND agent_type IN manifest.modules, order by installed_at, cap 5.
  2) Prompt assembly: agent._SYSTEM + `'\n\n## Active skills\n'` + per skill `'### {name} v{version}\n{prompt_template}'` with SkillInstallation.settings_json substituted via safe {{key}} templating (string replace, no eval); workflow list rendered as 'Suggested workflow: 1)...'.
  3) Broker: `effective_tools = agent.allowed_tools UNION (manifest.tool_permissions INTERSECT ALLOWED_TOOLS INTERSECT project_policy.allowed)`; the runtime's tool dispatch consults effective_tools and stamps `granted_by: {skill_slug|agent}` on each tool event (runtime/events.py).
  4) AgentRun gains injected_skills JSONB `[{slug, version}]` for replay; run view UI shows "Skills active" chips linking to the marketplace detail page.
  5) Project policy table row can deny a tool to skills even when the agent itself may use it (kill-switch).
  6) Telemetry: increment per-skill usage counters for the marketplace "used N times" display.

### WS8-2. Provenance graph: one edges table and a "Where did this number come from?" panel
- Source: SYS lens. Impact 5 · Feasibility 3 · **Priority 15** · Transformative-bet (implementable once deps
  land) · Depends on: WS3-1, WS2-3.
- **Problem:** ROADMAP Phase 1 promises "Research Memory Graph v1 using PostgreSQL edges" and PRODUCT.md calls
  the research graph the core moat, but ideas, runs, patches, documents, and papers are disjoint tables with
  zero cross-references beyond scattered FKs. Nobody can answer which run, commit, and conversation produced a
  number in the paper.
- **Proposal:** A single append-only provenance_edges table written automatically at every binding point (patch
  apply, anchor regeneration, figure render, asset acceptance, run launch), plus a BFS lineage API and a side
  panel in the paper editor that walks a macro or figure back through run → commit → patch → agent conversation
  with deep links.
- **Algorithm sketch:**
  1) Table provenance_edges(id, project_id, src_type varchar(30), src_id uuid, relation varchar(30), dst_type, dst_id, agent_run_id?, created_by?, metadata_json, created_at); indexes on (project_id, src_type, src_id) and (project_id, dst_type, dst_id). Node types: idea, library_paper, experiment, run, artifact, result_binding, figure_binding, asset_candidate, patch, commit, document_file, agent_run.
  2) One helper record_edge(db, ...) called from: experiment-created-from-idea, patch apply (agent_run→patch→commit), anchor/figure regeneration (run→binding→document_file), asset acceptance (run→candidate→document_file), run launch (run→commit via the existing ExperimentRun.git_commit).
  3) API: `GET /projects/{pid}/provenance/lineage?type=&id=&direction=up|down&depth<=5` → BFS over both index directions, resolving display labels through a per-type lookup registry; response `{nodes:[{type,id,label,href}], edges:[{src,dst,relation}]}`.
  4) UI: right-click a \Res macro or researchos:figure comment → "Lineage" panel; v1 renders an indented tree (number ← run ← commit ← patch ← conversation), each node deep-linking to its module page; v2 a small dag.
  5) Append-only: node soft-deletes grey out rather than break the chain — this is the auditability substrate every other idea writes into.

### WS8-3. Research pipelines: ideation → design → code → smoke run → paper as a first-class object
- Source: SYS lens. Impact 5 · Feasibility 2 · **Priority 10** · Transformative-bet · Depends on: WS8-1, WS2-3,
  WS6-1, WS3-5, WS8-2.
- **Problem:** Five agents exist (research, critic, coding, experiment, latex in agents/runtime/) but each is
  an isolated single-shot run launched from a separate page; the "one agent fabric" promise has no
  orchestration object, and an idea never flows into an experiment, a patch, or a paper asset without the user
  manually ferrying context.
- **Proposal:** A Pipeline object: a template DAG of stages, each backed by an existing agent type or execution
  primitive, with input mappers between stages and human approval gates. A Celery advance loop drives it; a
  pipeline page shows live stage cards over the existing WebSocket. This is also what makes the provenance
  graph dense, since consecutive stage outputs are auto-linked.
- **Algorithm sketch:**
  1) Tables: pipelines(id, project_id, template_slug, status, created_by); pipeline_stages(id, pipeline_id, seq, stage_type, status pending|running|awaiting_approval|done|failed, input_json, output_ref JSONB {agent_run_id|patch_id|run_id|candidate_id}, approved_by?).
  2) Template registry (hardcoded v1, two templates): 'idea-to-smoke' = ideation(ResearchAgent) → critic gate(CriticAgent, structured score; below threshold pauses with a revise loop) → design(experiment-design prompt variant producing config_json → creates Experiment+Run rows) → code(CodingAgent → PatchProposal on an agent branch) → smoke(sandbox runner job) → analysis(ExperimentAgent); 'result-to-paper' = analysis → table candidate → caption → inbox. Each stage declares input_mapper(prev_outputs)→agent context dict and gate: auto|human.
  3) Executor: Celery pipeline.advance(pipeline_id): next pending stage; human gate unapproved → set awaiting_approval + WS event and stop; else dispatch through the existing agents service / patch apply / runner spool, register a completion callback that stores output_ref and re-enqueues advance.
  4) Approval UI renders the stage's native artifact: diff viewer for patches, metric table for runs, candidate preview for assets.
  5) record_edge between consecutive outputs.
  6) Failure: stage failed → pipeline paused with retry/skip; all stage prompts versioned so smoke-test iteration on quality is measurable run-over-run.

---

## Transformative Bets (high impact, low feasibility-now — protect these on the roadmap)

These are NOT deprioritized. They are the ideas that make ResearchOS categorically different rather than
incrementally better; their low feasibility scores reflect quality-iteration or infra needs, not low value.
Build their plumbing early (most NOW-items above are exactly that plumbing).

| Bet | WS | Impact | Feas | What unblocks it | Why it's a moat |
|-----|----|--------|------|------------------|-----------------|
| Gap-matrix idea generation | WS5-1 | 5 | 2 | WS1-3 + WS1-4 + real-LLM smoke-testing weeks | Literature-grounded ideation nobody else structures deterministically |
| Research pipelines (idea→smoke→paper DAG) | WS8-3 | 5 | 2 | WS8-1, WS2-3, WS6-1, WS3-5, WS8-2 | The "one agent fabric" — turns 5 isolated agents into a research OS |
| Sandboxed execution runner | WS6-1 | 5 | 3 | WS2-3 + WS3-2; scaffold shippable now | Real smoke runs = idea validation with ground truth, plus real LaTeX |
| Provenance graph | WS8-2 | 5 | 3 | WS3-1 + WS2-3 | "Where did this number come from?" is the product's stated core moat |
| Paper Tutor (phase 2 of WS1-5) | WS1-5 | 5 | 3 | WS1-3 + prompt-depth iteration | Teach-me-this-paper with section-grounded quotes and quizzes |
| Novelty gauntlet | WS5-2 | 4 | 2 | WS1-2 + WS1-4 + threshold tuning | AI-Scientist-style iterative idea hardening with persisted rounds |
| Related-work weaver | WS4-4 | 4 | 2 | WS1-3, WS1-4, WS2-2 + prose iteration | Library → cited, reviewable LaTeX prose via the patch flow |
| SSH smoke-test runtime | WS6-2 | 4 | 2 | WS3-2 + real GPU host access | Real-server validation the owner explicitly wants for wishlist 3 |

---

## Cross-Workstream Dependency Spine

The load-bearing enablers, in the order they unlock the most downstream value:

1. **WS2-1 (coding agent read tools)** → unlocks WS2-2, WS2-5, WS2-6, and credible chat-to-diff (WS2-4).
2. **WS1-3 (full-text ingestion)** → unlocks WS1-5 phase 2, WS5-1, WS4-4.
3. **WS1-4 (pgvector embeddings)** → unlocks WS1-6, WS5-1, WS5-2, WS4-4.
4. **WS2-3 (git workspace)** → unlocks WS6-1 (snapshots), WS8-2 (commit nodes), run↔commit provenance.
5. **WS3-1 (result anchors)** → unlocks WS3-3, WS3-5, WS8-2.
6. **WS3-2 (telemetry contract)** → unlocks WS6-1 ingestion, WS6-2.
7. **WS8-1 (skill injection)** → makes WS3-6 style skills and future skill types actually reach agents.

A reasonable first sprint per engineer: WS1 → WS1-1+WS1-2; WS2 → WS2-1+WS2-2; WS3 → WS3-1+WS3-2;
WS4 → WS4-1; WS7 → WS7-1+WS7-2; WS8 → WS8-1.
