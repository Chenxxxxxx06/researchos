# Spec: Research — Paper Ingestion, Federated Search, Reading & Idea Plumbing

Workstream: **research** · Partition: `apps/api/researchos/research/**`
Realizes: INNOVATION_IDEAS WS1-1 (query compiler), WS1-2 (federation), WS1-3 (full-text
ingestion), WS1-6 (freshness feed, pull-based v1), WS1-4 (ranking; embeddings as STRETCH),
WS5-1 (gap-matrix idea gen, SHOULD), plus the import-verification security fix
(ARCHITECTURE_MAP §2 #19) and the `paper.sections` grounding tool for the tutor/explain path.

---

## Objective (user-visible outcome)

1. **Search that can actually be steered** (wishlist 1): category / date-window / author /
   title / abstract filters, latest-first sort, and "load more" pagination against arXiv —
   plus results from Semantic Scholar and OpenAlex merged and deduplicated, with citation
   counts and real venues, ranked by a hybrid of provider relevance, recency, and similarity
   to what is already in the project library.
2. **Papers become readable objects, not links** (wishlist 2): on import the server fetches
   the paper's ar5iv HTML, parses it into typed sections stored in `paper_sections`, and
   exposes them via `GET /papers/{id}/sections` and a `paper.sections` agent tool, so
   explanations can be grounded section-by-section with citation integrity.
3. **"Latest in my areas" feed** (wishlist 1): a cached, cursor-paginated feed of the newest
   arXiv submissions in the project's followed categories, with already-in-library markers.
4. **Imports can no longer be fabricated**: the server re-fetches metadata by external id at
   import time instead of trusting client-echoed payloads.
5. **Idea generation v2** (wishlist 3, SHOULD): a deterministic method×problem gap matrix
   mined from the library, with an LLM proposing underexplored cells as `Idea` rows whose
   supporting citations are validated against the library.

Everything works offline with the mock LLM provider and fixture-served HTTP; external calls
degrade to partial results or clear `provider_error` envelopes.

---

## Current state (concrete, file:line)

All paths relative to `apps/api/researchos/research/` unless noted.

- `providers/arxiv.py:40-43` — `_external_id` does `tail.split("v")[0]`: corrupts old-style
  ids (`solv-int/9701001` → `sol`, `math/0211159` → survives only by luck of having no `v`…
  actually `math/0211159` has no `v` so passes, but `cond-mat/0703470v2` → `cond-`). Version
  info is discarded entirely.
- `providers/arxiv.py:83-89` — exactly one request shape: `search_query=all:{raw query}`,
  `start=0`, `sortBy=relevance`. The `filters` argument (line 81) is **never read**. Raw user
  text is interpolated into the arXiv query language → operator injection (`AND`, `OR`,
  quotes) alters semantics (ARCHITECTURE_MAP §2 #15).
- `providers/arxiv.py:96-98` — `feedparser.parse` result used without checking `feed.bozo`;
  a malformed/error feed silently yields `[]`. No retry/backoff anywhere.
- `providers/arxiv.py:104-110` — abstract keeps hard line-wraps; `venue` hardcoded `"arXiv"`;
  DOI, categories, journal_ref dropped; `extra={"arxiv_id": entry_id}` stores the full URL,
  not the id.
- `providers/base.py:16-18` — `PaperSearchFilters` is only `year_from/year_to`; dead plumbing
  end-to-end (`service.py:46` never passes filters; `schemas.py:16-18` request has no filters
  field).
- `providers/registry.py:21-24` — single hardcoded provider; any other `PAPER_PROVIDER`
  value → 500.
- `service.py:48-78` — `import_papers` trusts the client-supplied `PaperResult` objects
  wholesale (the fabrication hole, `schemas.py:25-26`), and dedups via a per-item
  check-then-insert loop (N+1; concurrent import → IntegrityError 500).
- `models.py:17-41` — `Paper` has no doi / arxiv_id / category / citation-count / ingestion
  columns; `summary` (line 37) is never written; no sections table exists anywhere.
- `repository.py:55-61` — `list_ids_for_project` (citation-key set) is dead code.
- No ranking of any kind: search returns provider order (`ARCHITECTURE_MAP` §2 #20).
- `apps/api/researchos/agents/runtime/tools.py:99-125` (NOT owned) — tool registry has only
  `paper.search`, `library.list`, `workspace.tree`; broker auto-whitelists citations from any
  tool result carrying `source`/`external_id` items (lines 179-191) — we exploit this.
- `apps/api/researchos/agents/llm/mock.py:66-95` (NOT owned) — mock provider's
  `response_schema` handling knows only `files` (coding) and the critic object; a gap-matrix
  schema would get a critic-shaped answer.
- `apps/api/tests/test_paper_search.py` + `tests/fixtures/arxiv_sample.xml` — the recorded
  `httpx.MockTransport` fixture pattern to extend.

**Superseded prior decisions** (explicit):
- *Import provenance decision* (implicit in Phase 2 `schemas.py:25-26`: "client echoes the
  full PaperResult back") is **superseded**: the server now re-fetches metadata by
  `(source, external_id)` at import time. Rationale: the old contract lets any RESEARCHER
  insert fabricated papers that then become valid citation-whitelist entries — it defeats the
  whole "no fabricated citations" invariant (`providers/base.py:1-6` docstring).
- *`PAPER_PROVIDER` selects the single provider* (registry.py docstring "Phase 2 supports
  arXiv only") is **superseded**: the same env var now accepts a comma-separated list and
  yields a federated provider. Default `"arxiv"` keeps existing behavior byte-compatible.
- No PHASE1/PHASE3 decision is violated: citation keys stay `source:external_id`
  (ARCHITECTURE_MAP §5.2), native PG enums (P1-D11), UUID PKs app-side (P1-D10), 404-hiding
  via `ensure_access` on every new endpoint (P1-D6).

---

## Design (algorithms & data flow)

### D1. arXiv query compiler + id normalization fix + retry (MUST)

New pure functions in `providers/arxiv.py` (all unit-testable without I/O):

1. **Extended filter DTO** (`providers/base.py`):
   ```python
   SortOrder = Literal["relevance", "latest"]

   class PaperSearchFilters(BaseModel):
       year_from: int | None = Field(default=None, ge=1900, le=2100)   # kept, mapped to date window
       year_to: int | None = Field(default=None, ge=1900, le=2100)
       categories: list[str] = Field(default_factory=list, max_length=8)
       date_from: date | None = None
       date_to: date | None = None
       author: str | None = Field(default=None, max_length=200)
       title: str | None = Field(default=None, max_length=300)
       abstract: str | None = Field(default=None, max_length=300)
       sort: SortOrder = "relevance"
       offset: int = Field(default=0, ge=0, le=1000)

       @field_validator("categories")  # each must match ^[a-z-]+(\.[A-Za-z-]+)?$
   ```
2. **Sanitizer** `_sanitize_term(text: str) -> str`: strip `"` `(` `)` `{` `}` `[` `]` `:`;
   collapse whitespace. Prevents operator/grouping injection while keeping content words.
3. **Compiler** `compile_arxiv_query(query: str, filters: PaperSearchFilters | None) -> str`:
   - free text → sanitize, split on whitespace, drop bare `AND`/`OR`/`ANDNOT`/`NOT` tokens,
     AND-join as `(all:tok1 AND all:tok2 ...)`; empty free text contributes nothing.
   - `title`/`abstract`/`author` → phrase terms `ti:"..."`, `abs:"..."`, `au:"..."`
     (sanitized; single word → unquoted).
   - `categories` → `(cat:cs.LG OR cat:cs.CL)`.
   - date window → `submittedDate:[YYYYMMDD0000 TO YYYYMMDD2359]`; `year_from/year_to` are
     mapped to `Jan 1`/`Dec 31` when `date_from/date_to` absent. Open ends use
     `190001010000` / `now (UTC)`.
   - Join all groups with ` AND `. Result of no groups at all → `all:electron`-style error:
     raise `ProviderError("Empty query.")` (422 upstream via schema `min_length` on query OR
     categories present — see schemas).
4. **Request params**: `start=str(filters.offset)`, `max_results=str(limit)`,
   `sortBy = "submittedDate" if sort=="latest" else "relevance"`, `sortOrder=descending`.
5. **Id fix** (kills bug #16):
   ```python
   _VERSION_RE = re.compile(r"v(\d+)$")
   def _split_external_id(entry_id: str) -> tuple[str, str | None]:
       tail = entry_id.rsplit("/abs/", 1)[-1]
       m = _VERSION_RE.search(tail)
       return (_VERSION_RE.sub("", tail), m.group(0) if m else None)
   ```
   `solv-int/9701001` → (`solv-int/9701001`, None); `2401.01234v2` → (`2401.01234`, `v2`);
   `math/0211159` preserved. Version stored in `extra["arxiv_version"]`.
6. **Metadata capture**: `extra["arxiv_primary_category"]` from
   `entry.get("arxiv_primary_category", {}).get("term")`; `PaperResult.categories` from
   `entry.get("tags", [])`; `doi` from `entry.get("arxiv_doi")`; abstract whitespace-folded
   (`" ".join(summary.split())` — same normalization already applied to titles at line 104).
7. **Retry with backoff** — new `providers/retry.py`:
   ```python
   async def fetch_with_retry(
       fn: Callable[[], Awaitable[httpx.Response]], *,
       attempts: int = 3, base_delay: float = 0.5,
       retry_statuses: frozenset[int] = frozenset({429, 500, 502, 503, 504}),
       sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
   ) -> httpx.Response
   ```
   Retries `httpx.TransportError` and listed statuses with delay `base_delay * 2**i` plus
   ±25% deterministic jitter (`hash(i) % ...` — no `random` so tests are stable); re-raises
   the final failure. Tests inject `sleep=lambda _: asyncio.sleep(0)`. All three providers
   route their GETs through it.
8. **Bozo guard**: after `feedparser.parse`, `if feed.bozo and not feed.entries: raise
   ProviderError("arXiv returned an unparseable feed.")`.
9. **Fetch by ids** (for import verification): `ArxivProvider.fetch_by_ids(ids: list[str])`
   uses the API's `id_list={comma-joined}` param, one batched request (≤50 ids), same parse
   path, returns `list[PaperResult]`.

### D2. Semantic Scholar + OpenAlex providers, federation, dedup (MUST)

1. **`providers/semantic_scholar.py`** — `SemanticScholarProvider`, `name = "s2"`.
   - Search: `GET {settings.s2_api_base}/paper/search` with
     `query`, `offset`, `limit`,
     `fields=title,abstract,externalIds,year,venue,citationCount,openAccessPdf,authors,publicationDate,url`.
     Date window → `publicationDateOrYear={date_from}:{date_to}` (either side optional);
     categories/sort unsupported → ignored (federated layer handles `latest` sort).
   - Map: `external_id = paperId`; `doi = externalIds.DOI` (lowercased);
     `extra["arxiv_id"] = externalIds.ArXiv`; `pdf_url = openAccessPdf.url`;
     `citation_count = citationCount`; `published_at` from `publicationDate` (fallback
     `year → Jan 1`); `url = data.url or f"https://www.semanticscholar.org/paper/{paperId}"`.
   - No API key; keyless tier is rate-limited — one request per search call, honor
     `fetch_with_retry` on 429.
   - `fetch_by_ids`: sequential `GET /paper/{id}?fields=...` (import batches are ≤50 by
     schema; verified imports for s2 are rare); 404 → skip.
2. **`providers/openalex.py`** — `OpenAlexProvider`, `name = "openalex"`.
   - Search: `GET {settings.openalex_api_base}/works` with `search={q}`,
     `per-page={limit}`, `page={offset//limit + 1}`, and `mailto={settings.openalex_mailto}`
     when non-empty (polite pool). Filters:
     `filter=from_publication_date:YYYY-MM-DD,to_publication_date:YYYY-MM-DD`;
     `sort=publication_date:desc` when `sort=="latest"`. Categories ignored (no arXiv
     taxonomy mapping in v1).
   - Map: `external_id` = short OpenAlex id (`W…`, stripped of `https://openalex.org/`);
     `doi` from `ids.doi` (strip `https://doi.org/`, lowercase); abstract **reconstructed
     from `abstract_inverted_index`** (place each word at its positions, join by space);
     authors from `authorships[].author.display_name`; `venue` from
     `primary_location.source.display_name`; `citation_count = cited_by_count`;
     `extra["arxiv_id"]` extracted by regex from `primary_location.landing_page_url` /
     `locations[].pdf_url` when the host is `arxiv.org`.
   - `fetch_by_ids`: `GET /works/{id}` per id; 404 → skip.
3. **`providers/federated.py`** — `FederatedProvider(providers: list[PaperSearchProvider])`,
   `name = "federated"`.
   - `search`: `asyncio.gather` over
     `asyncio.wait_for(p.search(...), timeout=settings.provider_timeout_seconds)` with
     `return_exceptions=True`. Per-provider outcome recorded in
     `self.last_status: dict[str, str]` (`"ok" | "timeout" | "error:<code>"`), surfaced to the
     service (returned via a small `FederatedResult` tuple — see service). One failed
     provider never fails the search; **all** failed → `ProviderError`.
   - **Dedup/merge** `merge_results(by_provider: dict[str, list[PaperResult]]) -> list[PaperResult]`
     (pure function, heavily unit-tested):
     1. Normalizers: `normalize_doi` = lowercase, strip `doi:` / `https://doi.org/` prefixes;
        `normalize_arxiv_id` = `_VERSION_RE.sub("", id)`; `normalize_title` = NFKD → drop
        combining marks → lowercase → strip non-alnum → single-space.
     2. Union-find over all results. Union when any of: equal normalized DOI; equal
        normalized arXiv id (arxiv results use `external_id`, others `extra["arxiv_id"]`);
        equal normalized title; or (both still singleton) fuzzy pass:
        `difflib.SequenceMatcher(None, t1, t2).ratio() >= 0.92` **and** (same first-author
        lowercase last name **or** publication years within 1). n ≤ 3×25 = 75, O(n²) is fine —
        `rapidfuzz` deliberately not added (stdlib suffices at this scale).
     3. Merge each group with source priority `arxiv > s2 > openalex`:
        - identity fields (`source`, `external_id`, `url`, `pdf_url`, `published_at`) from
          the highest-priority member (keeps citation keys arXiv-first and importable);
        - `abstract`: longest non-empty; `authors`: from the member with the most authors;
        - `venue`: first non-null ≠ `"arXiv"` in priority order, else `"arXiv"`;
        - `doi`: first non-null; `citation_count`: max; `categories`: ordered union;
        - `extra["sources"] = [{"provider", "external_id", "url", "rank"}, ...]`
          (full provenance), `extra["arxiv_id"]` propagated to the merged record.
     4. Output order: RRF base ordering (see D5), recomputed by the ranking layer.
4. **`providers/registry.py`** rewrite: parse `settings.paper_provider` as a comma-separated
   list (`"arxiv"` default unchanged; e.g. `PAPER_PROVIDER=arxiv,s2,openalex`).
   `get_paper_provider(client)` returns the single provider or a `FederatedProvider`;
   `get_provider_by_name(name, client)` added for import verification. Unknown name →
   existing `config_error` 500, message lists known names.

### D3. Server-side import verification (MUST — closes the fabrication hole)

`service.py::PaperService.import_papers` is rewritten:

1. Request items are now **references**: `PaperImportRef {source: str, external_id: str}`
   with `model_config = ConfigDict(extra="ignore")` — old clients that still POST full
   `PaperResult` objects parse fine; every other field is discarded.
2. Group refs by `source`; for each, `get_provider_by_name(source).fetch_by_ids([...])`
   re-fetches authoritative metadata (arXiv: one batched `id_list` call). Ids the provider
   does not return → `skipped` with reason `"not_found"`. A provider error → all that
   source's refs `skipped` with reason `"provider_error"` (partial success is preserved).
3. **Dedup in two set-based queries** (replaces the N+1 loop):
   `PaperRepository.get_existing_keys(project_id, keys)` returns existing
   `(source, external_id)` pairs in one `SELECT ... WHERE tuple_(source, external_id).in_(...)`;
   a second `SELECT` matches incoming `doi`/`arxiv_id` against library columns for
   **cross-source** duplicates (e.g. the same paper previously imported from arXiv, now
   arriving as an OpenAlex ref). Matches are returned as already-imported rows.
4. Insert new `Paper` rows with the new columns (`doi`, `arxiv_id`, `primary_category` from
   `extra["arxiv_primary_category"]`, `citation_count`, `ingest_status=PENDING`); single
   commit. `IntegrityError` (concurrent duplicate) → caught, rolled back, re-read as
   existing (no more 500).
5. After commit, per newly created paper:
   `get_celery_client().send_task("ingestion.paper_fulltext", args=[str(paper.id)],
   queue="ingestion")` inside `try/except Exception` — a down broker logs a warning and
   leaves `ingest_status=PENDING` (the re-trigger endpoint recovers); import never fails on
   dispatch. (`get_celery_client` is imported from `common/celery_app.py` — import-only, no
   edit.)
6. Response: `ImportPapersResponse {imported: [PaperResponse], skipped: [{source,
   external_id, reason}]}` (reason ∈ `not_found | provider_error | invalid_source`).

### D4. Full-text ingestion → `paper_sections` (MUST)

New module `ingest.py`, single entry `async def ingest_paper(paper_id: uuid.UUID, *,
http_client: httpx.AsyncClient | None = None) -> PaperIngestStatus` (callable from the
worker task, the re-trigger endpoint's background dispatch, and tests):

1. Load paper (own session via `common/db.get_sessionmaker` pattern — mirror how
   `agents/runtime` builds sessions in the worker; when invoked from the API path a session
   is passed in via a thin wrapper `ingest_paper_with_session(db, paper_id, ...)` used by
   tests). Set `ingest_status=RUNNING`, commit, publish `paper.ingest.started`.
2. Resolve an arXiv id: `paper.arxiv_id` (populated for `source=="arxiv"` from
   `external_id`, else from federation's `extra["arxiv_id"]`). None → **fallback**: write a
   single section row from `paper.abstract` (kind `abstract`) if present, set
   `ABSTRACT_ONLY`, done.
3. Fetch chain (each via `fetch_with_retry`, timeout 20s, `follow_redirects=True`):
   a. `GET {settings.ar5iv_base_url}/{arxiv_id}` (ar5iv serves old-style ids verbatim:
      `https://ar5iv.labs.arxiv.org/html/math/0211159`);
   b. on non-200/exception → `GET {settings.arxiv_html_base_url}/{arxiv_id}` (native HTML
      for post-2023 papers);
   c. both failed → `ABSTRACT_ONLY` fallback as in step 2 when an abstract exists, else
      `FAILED` with `ingest_error` (truncated 500 chars).
4. Parse with **selectolax** (`HTMLParser`):
   - abstract: node `.ltx_abstract` → `seq=0, level=1, kind=ABSTRACT`.
   - for each top-level `section.ltx_section, section.ltx_appendix` (document order,
     `seq=1..N`): heading = text of the first `.ltx_title` child, stripped of leading
     numbering (`^\s*([\dIVXA-Z]+\.?)+\s*`); before extracting text, replace `math` nodes
     with their `alttext` attribute when present and drop `figure svg table.ltx_equation
     .ltx_bibliography` subtrees; body = `node.text(separator="\n", strip=True)` truncated
     to `settings.paper_section_max_chars` (default 20 000); subsections are flattened into
     the parent body (their `.ltx_title` lines remain inline) — v1 keeps `level` 1 for
     abstract, 2 for sections.
   - **kind classifier** (deterministic keyword map on lowercased heading, first match):
     `introduction→INTRODUCTION`, `background|preliminar|notation→BACKGROUND`,
     `method|approach|model|architecture|framework→METHOD`,
     `experiment|evaluation|setup|implementation→EXPERIMENTS`,
     `result|analysis|ablation|discussion→RESULTS`, `related→RELATED_WORK`,
     `conclusion|future|limitation→CONCLUSION`, appendix tag→`APPENDIX`, else `OTHER`.
   - Zero sections parsed but HTML fetched → `ABSTRACT_ONLY` fallback.
5. Persist idempotently (Celery `acks_late` redelivery-safe): `PaperSectionRepository.
   replace_for_paper(paper_id, rows)` = `DELETE WHERE paper_id=...` + bulk `add_all`, then
   set `ingest_status=SUCCEEDED|ABSTRACT_ONLY`, `ingested_at=now(UTC)`, single commit.
6. Publish `paper.ingest.completed` (payload `{paper_id, status, section_count}`) or
   `paper.ingest.failed` (`{paper_id, error}`) via `common/pubsub.publish_event` with an
   `EventEnvelope(resource_type="paper", resource_id=paper_id, ...)` (import-only usage;
   `ResourceType` literal extension is a cross-partition request).
7. Read paths: `PaperService.get_sections(actor, project_id, paper_id)` (VIEWER) returns
   status + ordered rows; `PaperService.sections_for_agent(actor, project_id, *, paper_key,
   kind=None, seq=None)` resolves `"source:external_id"` against the project library, filters
   by kind/seq, truncates bodies to 2 000 chars, and returns
   `{"results": [{source, external_id, title, url, seq, heading, kind, level, body}],
   "ingest_status": "..."}` — because items carry `source`/`external_id`, the existing
   `ToolBroker` (tools.py:179-191) automatically adds the paper to the citation whitelist:
   section-grounded explanations keep citation integrity with **zero** broker changes.
   Un-ingested paper → returns the abstract as a single pseudo-section plus the status so
   the agent degrades gracefully.

### D5. Hybrid ranking (MUST; embeddings STRETCH)

New module `ranking.py` (pure, deterministic, no I/O):

1. `tokenize(text)`: lowercase, `re.findall(r"[a-z0-9]{2,}", ...)`, minus a built-in ~50-word
   English stopword set.
2. `LibraryModel.build(docs: list[str])`: document frequencies over library docs
   (`title + " " + (abstract or "")`, newest ≤500), `idf = log((N+1)/(df+1)) + 1`; centroid =
   mean of L2-normalized tf-idf vectors (sparse `dict[str, float]`).
3. Components per candidate result:
   - `affinity` = cosine(candidate tf-idf vector, centroid) ∈ [0,1];
   - `recency` = `exp(-age_days / 730)` from `published_at` (None → neutral 0.35);
   - `provider_relevance` = reciprocal-rank fusion over provenance:
     `sum(1/(60 + rank) for each provider listing)` from `extra["sources"]` (single-provider
     search: one term), min-max normalized within the result set.
4. `score = 0.5*rrf + 0.3*affinity + 0.2*recency`; when the library has <3 papers, affinity
   weight folds into rrf (`0.8/0.0/0.2`) — cold-start ≈ provider order.
5. `PaperService.search` applies ranking when `filters.sort == "relevance"`; `"latest"`
   sorts by `published_at desc` (None last). Score and components exposed as
   `extra["score"]` / `extra["score_components"]` for UI bars. Model built per request from
   one library query (≤500 rows) — no cache in v1 (bounded, simple, correct).
6. **STRETCH** (pgvector): `papers.embedding vector(768)`; `hash_embed(text) -> list[float]`
   fallback (feature-hash unigrams+bigrams into 768 dims, L2-normalized, seeded, deterministic
   — works offline/mock); embed on import; centroid via SQL AVG; affinity component swaps to
   embedding cosine when embeddings exist. Also
   `GET /papers/{paper_id}/similar` via `ORDER BY embedding <=> :vec LIMIT 10`.

### D6. Freshness feed (MUST core; prefs override endpoint SHOULD)

New module `feed.py` (`FeedService`):

1. **Categories**: explicit prefs row (`research_feed_prefs.categories`) if present, else
   derived: `SELECT primary_category, count(*)` over the library, take top categories until
   ≥80% coverage, cap 5. Empty library + no prefs → 200 with `items: []`,
   `categories_used: []` (UI shows an actionable empty state).
2. **Query**: `ArxivProvider.search("", filters=PaperSearchFilters(categories=cats,
   sort="latest", offset=o), limit=n)` — the compiler must accept empty free text when
   categories are present (categories-only `search_query`).
3. **Cache**: Redis `SETEX` key `feed:{project_id}:{sha1(",".join(cats))}:{offset}:{limit}`,
   TTL `settings.feed_cache_ttl_seconds` (default 900), value = JSON items. On
   `ProviderError`: serve the cached page with `cached: true` if present, else re-raise
   (502 envelope) — offline degradation.
4. **Cursor**: opaque `base64url(json {"o": next_offset})`; `next_cursor=None` when the page
   came back short. **In-library markers** via the resurrected
   `PaperRepository.list_ids_for_project` (dead code #20 → alive): `in_library: bool` per item.
5. Import from the feed is just the normal verified import (`{source:"arxiv", external_id}`).
6. No Celery-beat daemon in v1 (no beat schedule exists anywhere; pull+cache gives the same
   UX at this scale) — WS1-6's push daemon is explicitly out of scope.

### D7. Gap-matrix idea generation v2 (SHOULD)

New module `gap_matrix.py`:

1. **Corpus**: newest ≤200 library papers; per paper one *method doc* (bodies of
   `kind=METHOD` sections when ingested, else title) and one *problem doc* (abstract first
   two sentences + title).
2. **Axis terms** (deterministic): top-25 tf-idf-weighted unigrams+bigrams per axis across
   the corpus (reusing `ranking.tokenize`/idf); a term must appear in ≥2 papers.
   `coverage = {(m, p) : some paper's docs contain both}`; **gap cells** = pairs with both
   supports ≥2 and no covering paper, ranked by `support(m) * support(p)`, top 10.
3. **One LLM call** via `agents.llm.factory.get_llm_provider(db, project_id)` (import-only):
   messages = system prompt (grounding rules: only cite provided keys) + a **tool-shaped
   context message** `LLMMessage(role="tool", content=json.dumps({"results": [{source,
   external_id, title}...]}))` listing the supporting papers + user message with the
   serialized matrix and gap cells; `response_schema = GAP_IDEAS_SCHEMA` with top-level
   property `ideas`. The tool-shaped message makes the existing mock citation extractor
   (`mock.py:24-38`) work unchanged; the mock needs only a new `"ideas"` schema branch
   (cross-partition request CP-4).
4. **Validation**: each proposed idea's `supporting_paper_keys` filtered against the library
   key set (`list_ids_for_project`); ideas with zero valid keys dropped. Survivors persisted
   as `Idea(status=DRAFT, metadata_json={"generated": True, "gap_type": ...,
   "supporting_paper_keys": [...], "cell": [m, p]})`.
5. Endpoint `POST /projects/{id}/ideas/generate` (RESEARCHER, CSRF, rate limit
   `enforce_rate_limit(f"idea_generate:{user.id}", limit=5)`), synchronous request (one
   bounded LLM call; instant under mock). Migration to the AgentRun/streaming machinery is a
   later iteration once an IDEATE agent type exists.

---

## API contract changes

All under the existing `router = APIRouter(prefix="/projects/{project_id}")`; auth, CSRF,
404-hiding and the error envelope follow the house pattern. **Route-ordering note**: the
literal routes `/papers/feed` and `/papers/feed/categories` MUST be declared before
`/papers/{paper_id}`.

1. **`POST /projects/{id}/papers/search`** (changed, backward-compatible)
   Request:
   ```json
   {"query": "diffusion planning", "limit": 20,
    "filters": {"categories": ["cs.LG", "cs.RO"], "date_from": "2025-01-01",
                "author": "Sergey Levine", "title": null, "abstract": null,
                "sort": "latest", "offset": 0}}
   ```
   `filters` optional (omitted → old behavior + ranking). Validation: `query` may now be
   empty (`min_length=0`) **iff** filters carry categories or fielded terms — enforced by a
   pydantic `model_validator`; otherwise 422.
   Response:
   ```json
   {"results": [{"source": "arxiv", "external_id": "2401.01234", "title": "...",
                 "abstract": "...", "authors": ["..."], "venue": "NeurIPS",
                 "published_at": "2024-01-03T00:00:00Z", "url": "...", "pdf_url": "...",
                 "doi": "10.1234/abc", "citation_count": 87, "categories": ["cs.LG"],
                 "extra": {"sources": [{"provider": "arxiv", "external_id": "2401.01234",
                                        "url": "...", "rank": 0}],
                           "score": 0.81,
                           "score_components": {"rrf": 0.9, "affinity": 0.7, "recency": 0.75}}}],
    "provider_status": {"arxiv": "ok", "s2": "timeout", "openalex": "ok"}}
   ```
   Errors: 422 empty query+filters; 429 rate limit; 502 `provider_error` only when **all**
   providers fail.

2. **`POST /projects/{id}/papers/import`** (changed — breaking response shape)
   Request (items need only source+external_id; extra fields ignored):
   ```json
   {"papers": [{"source": "arxiv", "external_id": "2401.01234"},
               {"source": "openalex", "external_id": "W2741809807"}]}
   ```
   Response `201`:
   ```json
   {"imported": [ /* PaperResponse, includes pre-existing duplicates */ ],
    "skipped": [{"source": "arxiv", "external_id": "9999.99999", "reason": "not_found"}]}
   ```
   Errors: 422 malformed; 502 never (per-source failures land in `skipped`).

3. **`GET /projects/{id}/papers/{paper_id}/sections`** (new, VIEWER)
   ```json
   {"paper_id": "…", "ingest_status": "succeeded", "ingested_at": "…", "ingest_error": null,
    "sections": [{"seq": 0, "level": 1, "kind": "abstract", "heading": "Abstract",
                  "body": "…", "char_count": 1023}]}
   ```
   404 unknown paper/non-member. `sections: []` while `pending|running|failed`.

4. **`POST /projects/{id}/papers/{paper_id}/ingest`** (new, RESEARCHER, CSRF)
   Re-triggers ingestion: sets status `pending`, dispatches `ingestion.paper_fulltext`.
   `202 {"paper_id": "…", "ingest_status": "pending"}`. 409 `{"error": {code:
   "ingest_running"}}` if currently `running`.

5. **`GET /projects/{id}/papers/feed?cursor=&limit=20`** (new, VIEWER)
   ```json
   {"items": [{ /* PaperResult fields */ , "in_library": false}],
    "next_cursor": "eyJvIjoyMH0", "categories_used": ["cs.LG", "cs.CL"], "cached": false}
   ```
   502 `provider_error` when arXiv unreachable and no cached page.

6. **`GET /projects/{id}/papers/feed/categories`** (new, VIEWER) →
   `{"categories": ["cs.LG"], "derived": true}`;
   **`PUT /projects/{id}/papers/feed/categories`** (SHOULD, RESEARCHER, CSRF) body
   `{"categories": ["cs.LG", "stat.ML"]}` (≤8, validated) → same shape, `derived: false`.

7. **`POST /projects/{id}/ideas/generate`** (SHOULD, RESEARCHER, CSRF)
   Request `{"max_ideas": 3}` (1–5). Response `201`:
   ```json
   {"ideas": [ /* IdeaResponse */ ], "gaps_considered": 10, "papers_used": 42}
   ```
   409 `{"error": {code: "library_too_small"}}` when <5 library papers; 429 rate limit.

8. **`GET /projects/{id}/papers/{paper_id}/similar`** (STRETCH, VIEWER) →
   `{"results": [{"paper_id": "…", "title": "…", "similarity": 0.83}]}`.

`PaperResponse` gains `doi`, `arxiv_id`, `primary_category`, `citation_count`,
`ingest_status`, `ingested_at` (all nullable/enum — additive, non-breaking for the web).

## WS events

Published from `ingest.py` via `common/pubsub.publish_event` (channel `ws:project:{id}`),
envelope per `websocket/envelopes.py` with `resource_type: "paper"`:

- `paper.ingest.started`   payload `{"paper_id": "<uuid>"}`
- `paper.ingest.completed` payload `{"paper_id": "<uuid>", "status": "succeeded" | "abstract_only", "section_count": 7}`
- `paper.ingest.failed`    payload `{"paper_id": "<uuid>", "error": "<message ≤500 chars>"}`

No client→server protocol changes. Frontend consumption is optional (list refetch on
`paper.ingest.completed`).

## DB changes

(For the migration agent — SQLAlchemy models change in `research/models.py`; no alembic files
authored here.)

New native enums:
- `paper_ingest_status`: `pending | running | succeeded | abstract_only | failed`
- `paper_section_kind`: `abstract | introduction | background | method | experiments |
  results | related_work | conclusion | appendix | other`

`papers` — add columns:
- `doi VARCHAR(255) NULL`, index `ix_papers_project_doi (project_id, doi)`
- `arxiv_id VARCHAR(64) NULL`, index `ix_papers_project_arxiv (project_id, arxiv_id)`
- `primary_category VARCHAR(32) NULL`
- `citation_count INTEGER NULL`
- `ingest_status paper_ingest_status NOT NULL DEFAULT 'pending'`
- `ingested_at TIMESTAMPTZ NULL`
- `ingest_error TEXT NULL`
Backfill: `UPDATE papers SET arxiv_id = external_id WHERE source = 'arxiv';` and
`UPDATE papers SET doi = lower(metadata_json->>'doi') WHERE metadata_json ? 'doi';`
existing rows keep `ingest_status='pending'` (re-ingestable via the endpoint).

`ideas` — add column: `metadata_json JSONB NOT NULL DEFAULT '{}'` (server default; no
backfill needed).

New table `paper_sections`:
`id UUID PK` (app-side), `created_at/updated_at TIMESTAMPTZ` (house mixins),
`paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE` (indexed),
`seq INTEGER NOT NULL`, `level INTEGER NOT NULL DEFAULT 1`,
`heading VARCHAR(500) NOT NULL DEFAULT ''`, `body TEXT NOT NULL`,
`char_count INTEGER NOT NULL`, `kind paper_section_kind NOT NULL DEFAULT 'other'`,
`UNIQUE (paper_id, seq)` (`uq_paper_section_seq`).

New table `research_feed_prefs`:
`project_id UUID PK REFERENCES projects(id) ON DELETE CASCADE`,
`categories JSONB NOT NULL DEFAULT '[]'`, `created_at/updated_at TIMESTAMPTZ`.

STRETCH only: `CREATE EXTENSION IF NOT EXISTS vector;`
`ALTER TABLE papers ADD COLUMN embedding vector(768);` + ivfflat cosine index.

## shared-schemas additions

- `events.ts`: new family
  `export const RESEARCH_EVENTS = ['paper.ingest.started', 'paper.ingest.completed',
  'paper.ingest.failed'] as const;` folded into `EVENT_TYPES`; `ResourceType` union gains
  `'paper'`. Payload interfaces: `PaperIngestCompletedPayload { paper_id: string; status:
  'succeeded' | 'abstract_only'; section_count: number }`,
  `PaperIngestFailedPayload { paper_id: string; error: string }`.
- The backend `websocket/envelopes.py` mirror (`ResourceType` literal + contract test
  vocabulary) is cross-partition request CP-6.

## New dependencies

- `apps/api/pyproject.toml`: **`selectolax>=0.3.21`** (ar5iv HTML parsing; wheel, no network
  at runtime beyond the fetch itself). Nothing else — fuzzy matching uses stdlib `difflib`
  (n≤75 pairwise; rapidfuzz deliberately skipped), TF-IDF is hand-rolled (~60 lines).
- `apps/worker`: none (worker depends on the API package editably).
- `apps/web`: none requested by this spec.

## File-by-file plan

Owned partition (`apps/api/researchos/research/`):

| File | Action | Contents |
|---|---|---|
| `providers/base.py` | modify | Extend `PaperSearchFilters` (D1.1); `PaperResult` gains `doi: str \| None`, `citation_count: int \| None`, `categories: list[str]`; new `PaperImportRef`; `PaperSearchProvider` protocol gains `async def fetch_by_ids(self, ids: list[str]) -> list[PaperResult]` |
| `providers/retry.py` | create | `fetch_with_retry` (D1.7), ~45 lines |
| `providers/arxiv.py` | modify | `compile_arxiv_query` + `_sanitize_term` + `_split_external_id` + sort/pagination params + bozo guard + retry + category/doi/version capture + `fetch_by_ids` (id_list). Keeps injectable client |
| `providers/semantic_scholar.py` | create | `SemanticScholarProvider` (D2.1), ~130 lines |
| `providers/openalex.py` | create | `OpenAlexProvider` incl. inverted-index abstract reconstruction (D2.2), ~160 lines |
| `providers/federated.py` | create | `FederatedProvider`, `merge_results`, union-find, normalizers (D2.3), ~200 lines |
| `providers/registry.py` | modify | comma-list parsing, `get_provider_by_name`, federated assembly (D2.4) |
| `providers/__init__.py` | modify | export new providers/DTOs |
| `ranking.py` | create | tokenizer, `LibraryModel`, RRF/recency/affinity, `rank_results` (D5), ~150 lines |
| `ingest.py` | create | `ingest_paper`, `ingest_paper_with_session`, ar5iv parser, kind classifier, WS publishes (D4), ~240 lines |
| `feed.py` | create | `FeedService`: category derivation, cache, cursor codec (D6), ~150 lines |
| `gap_matrix.py` | create (SHOULD) | matrix builder, `GAP_IDEAS_SCHEMA`, LLM call, validation/persist (D7), ~180 lines |
| `models.py` | modify | `Paper` new columns; `Idea.metadata_json`; new `PaperSection`, `ResearchFeedPref` models |
| `enums.py` | modify | `PaperIngestStatus`, `PaperSectionKind` (StrEnum) |
| `schemas.py` | modify | filters on `PaperSearchRequest` (+ empty-query validator), `provider_status` on response, `ImportPapersRequest`→refs, `ImportPapersResponse`, `PaperSectionResponse`, `SectionsResponse`, `IngestTriggerResponse`, `FeedResponse`/`FeedItem`, `FeedCategoriesRequest/Response`, `GenerateIdeasRequest/Response`; `PaperResponse` additive fields |
| `repository.py` | modify | `get_existing_keys`, `find_by_dois_or_arxiv_ids`, `list_library_docs(project_id, limit=500)`; new `PaperSectionRepository` (`replace_for_paper`, `list_by_paper`), `FeedPrefRepository` (get/upsert); `list_ids_for_project` now consumed by feed + gap matrix |
| `router.py` | modify | routes 3–7 above (feed routes **before** `/papers/{paper_id}`); search/import handlers updated |
| `service.py` | modify | `search` (filters → federation → ranking, provider_status passthrough), `import_papers` rewrite (D3), `get_sections`, `sections_for_agent`, `trigger_ingest`; `FeedService`/gap-matrix wiring |

Test files (new; no partition collision — consolidator: assign to research):

| File | Contents |
|---|---|
| `apps/api/tests/fixtures/arxiv_fielded.xml`, `arxiv_idlist.xml`, `arxiv_oldstyle.xml` | recorded Atom feeds (fielded query, id_list verification, old-style ids `math/0211159`, `solv-int/9701001`) |
| `apps/api/tests/fixtures/s2_search.json`, `s2_paper.json`, `openalex_search.json`, `openalex_work.json` | recorded provider payloads (incl. inverted-index abstract) |
| `apps/api/tests/fixtures/ar5iv_sample.html` | trimmed ar5iv document (abstract + 4 sections + appendix + math alttext) |
| `apps/api/tests/test_paper_search.py` | extend: compiler unit tests (injection neutralized, categories, date windows, empty-query+categories), id normalization table test, retry/backoff (fake sleep), bozo guard |
| `apps/api/tests/test_paper_federation.py` | s2/openalex parsing; merge_results dedup by DOI / arXiv id / fuzzy title; source-priority field merge; provider timeout → partial results + provider_status |
| `apps/api/tests/test_paper_ranking.py` | tokenizer/idf/cosine determinism; cold-start weight collapse; latest-sort path |
| `apps/api/tests/test_paper_ingest.py` | fixture HTML → section rows + kinds; abstract_only fallbacks; idempotent re-ingest; sections endpoint + tool-shaped `sections_for_agent` output; WS event publish (fake redis) |
| `apps/api/tests/test_paper_import_verify.py` | fabricated payload discarded (title comes from fixture, not client), not_found skips, cross-source doi dedup, N+1 gone (query-count assert optional), broker-down import still succeeds |
| `apps/api/tests/test_paper_feed.py` | category derivation 80% rule, cursor round-trip, cache hit (fakeredis-style via test redis), offline → cached page |
| `apps/api/tests/test_gap_matrix.py` (SHOULD) | matrix/gap mining determinism; mock-provider e2e generate → Idea rows with validated keys |

All tests follow the existing `httpx.MockTransport` + real-PG conftest pattern; **no external
network**; provider-pure tests need no DB.

## Cross-partition requests

- **CP-1 `apps/api/researchos/common/config.py`** — add Settings fields (defaults exactly):
  ```python
  s2_api_base: str = "https://api.semanticscholar.org/graph/v1"
  openalex_api_base: str = "https://api.openalex.org"
  openalex_mailto: str = ""                    # polite pool; empty → param omitted
  provider_timeout_seconds: float = 8.0
  provider_retry_attempts: int = 3
  ar5iv_base_url: str = "https://ar5iv.labs.arxiv.org/html"
  arxiv_html_base_url: str = "https://arxiv.org/html"
  feed_cache_ttl_seconds: int = 900
  paper_section_max_chars: int = 20_000
  ```
  (`paper_provider` keeps its name; its value is now parsed as a comma list — comment update
  only.) **Must land before/with this partition.**
- **CP-2 `apps/api/researchos/agents/runtime/tools.py`** (coding-git spec) — register:
  ```python
  async def _paper_sections(ctx: ToolContext, args: dict) -> dict:
      from researchos.research.service import PaperService
      return await PaperService(ctx.db, http_client=ctx.http_client).sections_for_agent(
          ctx.actor, ctx.project_id, paper_key=str(args.get("paper_key", "")),
          kind=args.get("kind"), seq=args.get("seq"))

  TOOL_REGISTRY["paper.sections"] = ToolSpec(
      name="paper.sections",
      description=("Read structured full-text sections of a library paper by "
                   "'source:external_id' key; optional kind or seq filter."),
      parameters={"type": "object", "properties": {
          "paper_key": {"type": "string"}, "kind": {"type": "string"},
          "seq": {"type": "integer"}}, "required": ["paper_key"]},
      impl=_paper_sections)
  ```
- **CP-3 `apps/api/researchos/agents/runtime/research_agent.py`** — `allowed_tools` becomes
  `["paper.search", "library.list", "paper.sections"]`.
- **CP-4 `apps/api/researchos/agents/llm/mock.py`** — in the `response_schema` branch, before
  the critic fallback: `if "ideas" in props:` return
  `{"ideas": [{"title": "Bridge gap: <first user-message line ≤60 chars>", "description":
  "Deterministic mock idea grounded in provided papers.", "hypothesis": "H1",
  "gap_type": "coverage", "supporting_paper_keys": cited[:2]}]}` (uses the existing `cited`
  extraction — the gap-matrix caller supplies a tool-shaped context message).
- **CP-5 `apps/worker/researchos_worker/tasks/ingestion.py`** (new file, worker partition):
  ```python
  from researchos.common.asyncio_runner import run_async_task
  from researchos.research.ingest import ingest_paper
  from ..app import app

  @app.task(name="ingestion.paper_fulltext")
  def paper_fulltext(paper_id: str) -> str:
      run_async_task(lambda: ingest_paper(uuid.UUID(paper_id)))
      return paper_id
  ```
  plus import in `tasks/__init__.py`. Queue `ingestion` already exists (`worker/queues.py`).
- **CP-6 `apps/api/researchos/websocket/envelopes.py` + `packages/shared-schemas/src/events.ts`
  + `apps/api/tests/test_ws_contract.py`** — add `"paper"` to `ResourceType`; add
  `RESEARCH_EVENTS` (exact strings in "WS events" above) to the TS vocabulary and the
  contract test.
- **CP-7 `apps/api/researchos/models.py`** — aggregator imports gain
  `PaperSection, ResearchFeedPref` from `researchos.research.models`.
- **CP-8 `apps/web`** (web spec, non-blocking): import call may slim its payload to
  `{source, external_id}` and must read the new `{imported, skipped}` response; optional:
  filter bar for search, sections viewer, feed tab, ingest-status chip. Until then the old
  client still works for search/import (request stays parseable; import response shape is the
  one breaking change to coordinate).

## MUST / SHOULD / STRETCH breakdown

**MUST** (core, ~1500 changed lines + tests):
1. Query compiler + sanitizer + sort/pagination + retry/backoff + bozo guard + external-id
   fix + metadata capture (D1).
2. S2 + OpenAlex providers, federation with per-provider timeouts, three-tier dedup + merge,
   `provider_status` (D2) — registry comma-list.
3. Server-side verified import + set-based dedup + `{imported, skipped}` response (D3).
4. Full-text ingestion (`ingest.py`), `paper_sections` model/repo, `GET sections`,
   `POST ingest` re-trigger, `sections_for_agent` (D4) + Celery dispatch (CP-5).
5. Hybrid ranking v1 (TF-IDF affinity + RRF + recency) (D5).
6. Feed endpoint with derived categories, Redis cache, cursor, in-library markers (D6).
7. Fixtures + tests for all of the above.

**SHOULD** (degrade by dropping whole units):
1. `PUT /papers/feed/categories` prefs override (+ `research_feed_prefs` table — if dropped,
   the table still ships in models but derivation-only is used).
2. Gap-matrix idea generation (D7) + `Idea.metadata_json` + CP-4 mock branch.
3. WS `paper.ingest.*` events (CP-6) — ingestion works without them (status is polled).
4. `extra["score_components"]` breakdown (keep bare `score` if squeezed).

**STRETCH**:
1. pgvector `papers.embedding vector(768)` + deterministic hash-embedding fallback +
   embedding-based affinity + `GET /papers/{id}/similar`.

## Acceptance criteria (verifiable via local gates + code review + CI tests)

1. `ruff check` and `mypy` pass over `apps/api` with the new modules; `tsc`/`next build`
   unaffected (no owned web files).
2. Code review: `_split_external_id("http://arxiv.org/abs/solv-int/9701001")` returns
   `("solv-int/9701001", None)`; `.../abs/2401.01234v2` → `("2401.01234", "v2")` —
   asserted in `test_paper_search.py` (CI).
3. Code review: `compile_arxiv_query('cats" OR all:dogs', filters)` contains no user-supplied
   quotes/parens/`OR` operators (injection neutralized) — asserted in CI tests.
4. `import_papers` contains **no** field copied from client input other than
   `source`/`external_id` (grep-verifiable in `service.py`); title/abstract/url provably come
   from the provider fixture in `test_paper_import_verify.py`.
5. Search with `sort="latest"` orders by `published_at` desc; with default sort each result
   carries `extra["score"] ∈ [0,1]` — CI tests.
6. `merge_results` collapses the same paper arriving from three providers into one result
   with `extra["sources"]` length 3, arXiv identity, max citation_count, non-arXiv venue —
   CI test.
7. Ingesting the ar5iv fixture yields ≥5 `paper_sections` rows with `kind` classification
   (`introduction`, `method`, `experiments`, `results`/`conclusion`, `appendix`) and
   `ingest_status='succeeded'`; a paper with no arxiv_id and an abstract →
   `abstract_only` with exactly one section — CI test.
8. Feed returns `in_library=true` for an imported fixture paper and round-trips the cursor;
   a second call within TTL is served from cache (assert via a transport call counter) — CI.
9. All new endpoints call `ensure_access` with the roles listed above (code review); unknown
   project → 404 (covered by extending `test_research_permissions.py` patterns).
10. With `LLM_PROVIDER=mock`, `POST /ideas/generate` (if SHOULD ships) persists ≥1 Idea whose
    `metadata_json.supporting_paper_keys` all exist in the library — CI test.
11. No test performs external network I/O (MockTransport everywhere; conftest grep).

## Test plan (CI-run pytest; no external network)

Listed per file in the file-by-file table above; conventions: provider-pure tests use
`httpx.MockTransport` handlers that also **assert outgoing request params** (e.g. that
`search_query` contains `cat:cs.LG`, `start=20`, `sortBy=submittedDate`; that OpenAlex gets
`mailto` when configured); service-level tests reuse the existing PG/Redis conftest
(`researchos_test` DB, Redis db 15) exactly like `test_paper_library.py`. Retry tests inject
a recording fake `sleep`. Ingestion tests call `ingest_paper_with_session` directly with a
fixture-backed client (no Celery). Feed cache tests use the test Redis. Playwright: none
owned here (web partition may add a search-filters smoke later).

## Explicitly out of scope

- Celery-beat push feed / nightly refresh daemon (WS1-6 full form) — pull+cache only.
- PDF text extraction (pypdf), GROBID, MinIO storage of PDFs; reading-room UI and the EXPLAIN
  tutor agent (WS1-5) — this spec only lands their grounding substrate (`paper.sections`).
- Section-anchor citation keys (`arxiv:x#sec:5`) — whitelist stays paper-level (agents
  partition owns `citations.py`).
- Crossref provider; provider credentials/API keys of any kind.
- Novelty gauntlet (WS5-2); `Idea.novelty_score` remains unwritten.
- Alembic migration authoring and shared-schemas file edits (consolidated centrally).
- Any frontend changes (contracts declared in CP-8 only).
