# Spec: frontend-ide — Chat-to-diff IDE, git timeline, hardened realtime client

Realizes INNOVATION_IDEAS WS2-4 (coding chat with inline diff cards), the frontend half of WS2-2
(per-hunk accept) and WS2-3 (git timeline/revert), and fixes gaps #54/#55/#56/#63/#65 from
ARCHITECTURE_MAP §2/§4. Owner wishlist 5: "chat maps directly to diffs, git rollback/traceability".

**Partition (files owned):** `apps/web/features/ide/**`, `apps/web/lib/websocket/**`,
`apps/web/lib/api/{codingAgent,patches,git,workspace}.ts`, `apps/web/lib/ide/**`.

**Backend dependency note:** `docs/specs/coding-git.md` did not exist when this spec was written.
Every backend contract this spec consumes is stated exactly in "API contract changes" as an
**ASSUMED** contract, and every one has a client-side feature-detect fallback so this partition
ships and builds even if the backend workstream is cut or shaped differently. The consolidator
must reconcile the ASSUMED blocks against coding-git.

---

## Objective (user-visible outcome)

1. The IDE right rail becomes a real coding chat: session-scoped message history, live token
   streaming, tool-call chips ("reading `apps/api/...`"), and — when a run produces a patch — an
   **inline diff card in that chat turn** with per-file collapsible diffs, per-hunk accept/reject
   checkboxes, Apply-all / Reject-all, and a status pill that updates in place. The chat IS the
   change history.
2. The left-rail git stub becomes a **timeline**: real status (dirty files), commit list where
   patch commits carry chips linking back to their chat turn and patch, per-commit diff viewer,
   and one-click revert with inline confirmation. Chat turn ↔ patch ↔ commit is a navigable
   triangle in both directions.
3. A WS blip no longer freezes every live surface in the app: the shared socket reconnects with
   exponential backoff + jitter, optionally heartbeats, replays missed persisted events via the
   existing REST events endpoint, and applies tokens ordered and deduped. `ResearchChat`,
   `PaperAssistant`, and `AnalysisPanel` (other partitions) gain this for free because the public
   hook API is preserved.
4. Editor stops losing work: closing a dirty tab asks first, leaving the page with dirty buffers
   warns, background refetches never clobber a dirty buffer, and diff cards / search results can
   open a file at a specific line.
5. All IDE surfaces get real empty/loading/error states styled with the WS7 semantic design
   tokens (with a neutral-class fallback if that workstream is cut).

## Current state (concrete, file:line)

- `apps/web/features/ide/CodingAssistant.tsx:16-22` — one-shot textarea; on success fires
  `for (let i = 1; i <= 5; i++) setTimeout(... invalidateQueries(['patches']), i*1200)`. No
  streaming, no history, run failures invisible (gap #56).
- `apps/web/features/ide/PatchReviewPanel.tsx:16` — `refetchInterval: 5000` polling; patch list is
  physically detached from the request that produced it. `:22` hardcoded status→amber/emerald
  class map.
- `apps/web/features/ide/PatchDiff.tsx:12-17` — diff renders **live file** (`['file', projectId,
  file.path]` query) vs `new_content`, not the recorded base → stale patches show misleading
  diffs (gap #36). One Monaco DiffEditor per file (heavy).
- `apps/web/features/ide/EditorPane.tsx:27-33` — propose-patch builds `change_type:'modify'` only,
  `base_sha: file.data?.sha ?? null` (can be stale/null), and never clears the buffer after
  success → duplicate proposals (gap #55). `:47` `isDirty = buffers[path] !== undefined` — any
  keystroke marks dirty forever even if reverted. No dirty-close guard, no beforeunload, no
  reveal-at-line capability.
- `apps/web/lib/store/ide.ts:31-41` — `closeTab` silently `delete buffers[path]` (gap #65);
  `bottomHeight`/`rightWidth` fields have no setters. **Not in this partition** — replaced by an
  owned store, see Cross-partition requests.
- `apps/web/features/ide/GitStatusPanel.tsx:12-18` — renders the stub provider's always-clean pill
  (`git/provider.py:44-45` hardwired). No log, no diff, no revert.
- `apps/web/lib/websocket/client.ts:15-28` — bare `new WebSocket`, no reconnect / backoff /
  heartbeat / `onerror`; malformed frames swallowed at `:23-25` (gaps #63, silent-failure #12).
- `apps/web/lib/websocket/useProjectAgentEvents.ts:37-49` — one socket **per consuming
  component**; token deltas appended in arrival order with no seq/dedup (`:63-66`); `trackRun`
  (`:51-53`) never replays, so events between POST and WS subscribe are lost; the REST replay
  endpoint (`apps/api/researchos/agents/router.py:72-81`, client fn
  `apps/web/lib/api/agents.ts:60-66`) is never called (gap #54).
- `apps/web/lib/api/patches.ts:12` — `hunks: unknown[]` (PatchHunk table is dead weight);
  `applyPatch:69-73` takes no body (all-or-nothing).
- `apps/web/lib/api/git.ts:17-19` — `getGitStatus` only.
- `apps/web/lib/api/codingAgent.ts:3-11` — single `createCodingRun`; no sessions, no history.
- `apps/web/lib/ide/monaco.tsx:7` — CDN loader, always light theme. `language.ts:3-18` no
  tex/bib/rust/go.
- `apps/web/app/(workspace)/projects/[projectId]/ide/page.tsx:19-48` — composes the five current
  components with hardcoded neutral classes. **Not in this partition.**
- Backend today: WS gateway is a push-only relay (`websocket/router.py:69-79`), only
  `agent.run.*` events exist, coarse events are persisted and replayable via
  `GET /projects/{id}/agents/runs/{run_id}/events?after_seq=` — tokens are live-only
  (`runtime/events.py`).

## Design (algorithms & data flow)

### D1. Shared project socket manager (`lib/websocket/client.ts`, rewritten)

One socket per `(browser tab, projectId)` regardless of how many components subscribe.

Data structures:

```ts
type ConnectionState = 'connecting' | 'open' | 'reconnecting' | 'offline' | 'closed';
interface SocketStatus { state: ConnectionState; attempt: number; lastOpenAt: number | null }
type Listener = (env: EventEnvelope) => void;
type StatusListener = (s: SocketStatus, kind: 'open' | 'reopen' | 'down') => void;

class ProjectSocketManager {
  private sockets = new Map<string, ManagedSocket>();      // key: projectId
  acquire(projectId): { subscribe(l: Listener): () => void;
                        subscribeStatus(l: StatusListener): () => void;
                        release(): void }
}
```

`ManagedSocket` algorithm:

1. **Connect** to `projectWsUrl(projectId)` (unchanged URL derivation). State `connecting`.
2. **onmessage**: `JSON.parse`; on parse failure `console.warn('[ws] malformed frame', ...)` and
   drop (no longer silent). If the object has a `type` field (control frame) handle internally
   (`pong` → note capability + clear pending-pong timer; unknown control types ignored). If it has
   an `event_type` field, run **dedupe**: an LRU `Set<string>` of the last 512 `event_id`s per
   socket; duplicates dropped. Otherwise fan out to all listeners synchronously.
3. **Reconnect with exponential backoff + full jitter**: on `close`/`error` while any subscriber
   holds a ref: `delay = random(0.5, 1.0) * min(30_000, 1_000 * 2**attempt)`; `attempt` resets to
   0 after a connection stays open ≥ 5s or delivers any frame. State `reconnecting`. When
   `navigator.onLine === false`, state `offline` and wait for the `online` window event instead of
   timers. A `visibilitychange`→visible event while down triggers an immediate retry (skip the
   remaining delay).
4. **Heartbeat (capability-probed)**: on every `open`, send one
   `{"type":"ping","ts":Date.now()}` probe. If a `{"type":"pong"}` arrives within 10s, mark the
   server pong-capable (module-level flag, remembered for the session) and start the loop: ping
   every 25s; missing 2 consecutive pongs → `ws.close()` (which routes into the reconnect path).
   If the probe gets no pong (today's push-only gateway ignores client frames — harmless), never
   ping again this session and rely on close/error/offline signals only. This makes the client
   correct against both the current gateway and the requested upgraded one.
5. **Reopen notification**: on every successful open *after* the first, notify status listeners
   with `kind:'reopen'` — the trigger for REST replay reconciliation (D2).
6. **Refcount**: `release()` decrements; at zero, close the socket and delete the map entry.
   Back-compat shim `connectProjectEvents(projectId, onEvent)` is kept, implemented over
   `acquire`, returning a `WebSocket`-shaped facade with `close()` → `release()` (no external
   callers exist outside this partition, but keeps the diff honest).

### D2. Run-event reducer with ordering, dedupe, and replay (`lib/websocket/useProjectAgentEvents.ts`, rewritten; public API preserved)

Public API is **unchanged** — `useProjectAgentEvents(projectId): { runs, trackRun }` with the
exact `LiveRun` / `LiveToolCall` shapes currently imported by `ResearchChat.tsx`,
`AgentRunMessage.tsx`, `ToolCallChip.tsx`, `PaperAssistant.tsx`, `AnalysisPanel.tsx` (other
partitions; zero edits needed there). Internal additions per run (not exported, stored in a ref):

```ts
interface RunInternal { lastCoarseSeq: number;   // max persisted-event seq folded so far
                        lastTokenSeq: number;    // -1 when server doesn't send token seq
                        terminal: boolean }
```

Algorithm:

1. Subscribe once via the manager. Envelope fold rules (idempotent reducer, safe to re-apply):
   - `agent.run.token`: if `payload.seq` is a number, apply only when `seq > lastTokenSeq`
     (drop stale/dup), update `lastTokenSeq`; when `seq` is absent (current backend), rely on the
     manager's `event_id` dedupe and apply in arrival order (per-connection FIFO is ordered).
   - `tool_call.started/completed`: **upsert keyed by `payload.seq`** (replaces today's
     append+map, which double-appends on replay).
   - Status transitions are monotonic: `queued < running < (completed|failed|cancelled)`; a
     replayed `started` can never un-complete a run. `completed.output` replaces accumulated text
     (already the backend contract — fixes any token gap).
2. **`trackRun(runId)`** now also fires an immediate catch-up replay:
   `getAgentRunEvents(projectId, runId, -1)` (import from `@/lib/api/agents` — read-only import
   of a non-owned file is fine) and folds results, closing the POST→subscribe race (gap #54).
   Errors are swallowed with a `console.warn` (run may 404 for a moment right after create →
   retry once after 1s).
3. **On `reopen`**: for every tracked non-terminal run, `getAgentRunEvents(projectId, runId,
   lastCoarseSeq)` and fold. Persisted events carry `seq`; fold sets
   `lastCoarseSeq = max(seq)`. Tokens are not persisted (ARCHITECTURE_MAP §3.6) so mid-run text
   gaps are healed at `completed`; if the ASSUMED `agent.run.text_snapshot` event (see WS events)
   lands, its `{text, through_seq}` payload replaces `run.text` during replay — pure additive.
4. Run map is bounded: terminal runs beyond the 50 most recent are evicted (fixes unbounded map,
   gap #54 tail).
5. New optional export `useProjectConnection(projectId): SocketStatus` for the status pill —
   additive, no consumer outside this partition required.

### D3. Coding chat with inline diff cards (`features/ide/chat/*`)

Component tree (right rail, replaces `CodingAssistant` + `PatchReviewPanel`):

```
CodingChat(projectId)
 ├─ SessionBar         — session switcher + "New session" (hidden in fallback mode)
 ├─ TurnList           — scrollable; per turn: <ChatTurn>
 │    ├─ user bubble (turn.user_message)
 │    ├─ assistant bubble: live text (streaming) or persisted output_text
 │    ├─ IdeToolCallChip row — "⚙ workspace.read apps/api/…/service.py ✓" from live tool events
 │    │   or persisted replay events; args preview: path/pattern arg when present
 │    └─ DiffCard(patchId)  — iff the turn produced a patch
 └─ Composer           — textarea, mod+Enter submits, disabled while a run in this session is live
```

Data flow, numbered:

1. **Session resolution** (`lib/ide/useCodingSessions.ts`): try `listSessions(projectId)`
   (ASSUMED endpoint). On HTTP 404/405 → `{ supported:false }` and the UI runs in **fallback
   mode**: one implicit session whose turns are `listAgentRuns(projectId)` items filtered
   client-side to `agent_type === 'coding'` (cast via local type; first page), mapped to the same
   `CodingTurn` shape. React Query `queryKey: ['coding-sessions', projectId]`,
   `retry: (n, err) => !(err instanceof ApiError && (err.status===404||err.status===405))`.
2. **History**: `listTurns(projectId, sessionId)` → ascending `CodingTurn[]`. Live overlay: for
   each turn whose `agent_run_id` is in the hook's `runs` map and non-persisted-final, the live
   accumulator wins for text/toolCalls/status (same persisted+live merge pattern as
   `ResearchChat.tsx:42-45`, but keyed by run id, not order-dependent — fixes gap #53's fragility
   for this surface).
3. **Send**: `sendMessage(projectId, sessionId, text)` (fallback: `createCodingRun`) →
   `trackRun(agent_run_id)` → optimistic turn appended to the query cache (status `queued`,
   user_message = text). No timers, no blind invalidation: the `agent.run.completed|failed`
   fold for that run triggers exactly one invalidation of `['coding-turns', sessionId]`,
   `['patches', projectId]` and — when `output.patch_id` present — a prefetch of
   `['patch', patchId]`.
4. **DiffCard(patchId)** — the heart. `useQuery(['patch', projectId, patchId], getPatch)`.
   Header: summary, `N files · +A −D` (computed from diff), status pill
   (pending/applied/rejected/conflict/partially-applied), applied-commit chip (`short_sha`, click
   → opens git timeline and selects the commit) when `applied_commit_sha` present. Body: one
   `FileDiffSection` per file, collapsed by default beyond the first 3 files:
   - Display diff source order: (a) if `file.base_content !== undefined` (ASSUMED field) →
     compute hunks client-side with `lib/ide/diff.ts` from `base_content` vs `new_content`;
     (b) else if server `hunks[]` non-empty → render those verbatim; (c) else (create/delete or
     legacy payload) → whole-file added/removed rendering from `new_content`/nothing. **Never**
     diff against the live file (supersedes `PatchDiff.tsx` behavior; the misleading-diff bug
     dies with the file).
   - `HunkView`: static `<pre>`-table rows (old/new line numbers, `+`/`−` gutter, token-colored
     via CSS only — no Monaco instance per hunk; Monaco is reserved for the "Open full diff"
     action which opens the existing `MonacoDiff` in a takeover panel with
     `original = base_content ?? ''`, `modified = new_content ?? ''`).
   - Per-hunk checkbox (default checked) when the patch is `pending` **and** partial apply is
     supported (see 5); header shows "Apply 3 of 5 hunks" when a subset is selected. File header
     has "open at line" → `openFileAtLine(path, firstSelectedHunk.new_start)`.
5. **Apply / Reject**: footer buttons `Apply all` / `Reject all`; when any checkbox is unchecked
   the primary becomes `Apply selected (k/n)` calling
   `applyPatch(projectId, patchId, selections)` (ASSUMED body). Feature detect: if that call
   fails with 400/422 `code:'unsupported'` (or the patch has no server hunk ids), the checkboxes
   hide and only whole-patch Apply/Reject remain (today's API). On success: write the returned
   patch/apply-result into the `['patch', patchId]` cache **in place** (status pill flips without
   refetch), then invalidate `['patches']`, `['workspace-tree']`, `['file', projectId]` (prefix),
   `['git-status']`, `['git-log']`. Conflict result renders the existing conflicts list inline in
   the card (red panel, per-path reason) — the card stays in the chat as the permanent record.
6. **Traceability anchors**: each turn root gets `id={"turn-"+agent_run_id}`; the git timeline
   navigates via `ideStore.revealTurn(runId)` → CodingChat scrolls the anchor into view and
   flash-highlights it (2s token-colored ring).

### D4. Client-side line diff (`lib/ide/diff.ts`, new — zero dependencies)

Myers O(ND) greedy diff on line arrays (the standard algorithm), then hunk grouping:

```ts
export interface DiffLine { kind: 'ctx' | 'add' | 'del'; oldNo: number | null; newNo: number | null; text: string }
export interface DisplayHunk { header: string; oldStart: number; oldLines: number;
                               newStart: number; newLines: number; lines: DiffLine[] }
export function diffLines(base: string, next: string): DiffLine[]        // Myers, ~90 lines
export function groupHunks(lines: DiffLine[], context?: number /* =3 */): DisplayHunk[]
export function diffStats(lines: DiffLine[]): { additions: number; deletions: number }
export function toDisplayHunks(serverHunks: PatchHunk[]): DisplayHunk[]  // parse unified content
```

Guards: inputs capped at 20_000 lines each — beyond that render "diff too large, open full diff"
(Monaco handles big files better). Pure functions, no DOM — unit-testable if web test infra ever
lands; correctness is asserted indirectly by the Playwright spec (a known patch produces known
+/− counts).

### D5. Git timeline (`features/ide/git/*`, replaces GitStatusPanel stub)

```
GitTimelinePanel(projectId)
 ├─ StatusHeader   — branch, clean/dirty pill from real porcelain; dirty file list expandable,
 │                   per-file click → open in editor
 ├─ CommitList     — useQuery(['git-log', projectId], getGitLog); vertical timeline: dot,
 │                   relative time, first line of message; patch commits get chips:
 │                   [patch ⌗] → prefetch+open that DiffCard context, [chat ↩] → revealTurn(run)
 ├─ CommitDiffViewer — on select: getCommitDiff(sha); per-file FileDiffSection reusing D4
 │                   (old_content vs new_content), same HunkView renderer (checkboxes disabled)
 └─ RevertRow      — inline confirm (no modal dep): "Revert creates an inverse commit —
                     ⚠ working tree must be clean" [Revert] [Cancel]; on 409 git_dirty or
                     git_revert_conflict renders the error envelope message inline
```

Flow: revert success → invalidate `['git-log']`, `['git-status']`, `['workspace-tree']`,
`['file', projectId]` prefix, and open the new revert commit's diff. Feature detect: if
`getGitLog` returns 404 (git workstream not landed), the panel renders the StatusHeader from the
existing stub status plus an EmptyState: "Git history arrives with the git-backed workspace." —
never a crash. Log pagination: "Load more" via `offset` (no infinite scroll dependency).

WS-driven freshness (SHOULD): if `git.commit.created` / `patch.status_changed` events (ASSUMED)
arrive on the shared socket, invalidate `['git-log']` / patch cache respectively; without them,
freshness comes from our own mutation invalidations + `refetchOnWindowFocus` (default on).

### D6. Editor UX (`features/ide/EditorPane.tsx` + `lib/ide/store.ts`, new owned store)

New store (replaces the un-owned `lib/store/ide.ts`; `EditorPane`/`FileTree` are its only
consumers and both are owned):

```ts
interface Buffer { content: string; baseSha: string | null }   // sha of server content it forked from
interface IdeState {
  tabs: string[]; active: string | null;
  buffers: Record<string, Buffer>;
  pendingReveal: { path: string; line: number } | null;
  selectedCommitSha: string | null; highlightTurnRunId: string | null;
  rightTab: 'chat' | 'git';                       // right-rail mode switch
  openTab(path: string): void;
  openFileAtLine(path: string, line: number): void;   // openTab + set pendingReveal + rightTab unchanged
  requestCloseTab(path: string): 'closed' | 'needs-confirm';  // dirty ⇒ needs-confirm
  forceCloseTab(path: string): void;
  setBuffer(path: string, content: string, serverContent: string, serverSha: string | null): void;
  reconcileServer(path: string, serverContent: string, serverSha: string | null): void;
  revealTurn(runId: string): void; selectCommit(sha: string | null): void;
}
```

Rules, numbered:

1. **Dirty definition**: a buffer exists ⇔ it differs from the server content it forked from.
   `setBuffer` deletes the buffer when `content === serverContent` (typing back to original
   un-dirties — fixes `EditorPane.tsx:47`).
2. **Refetch-clobber**: `EditorPane` render value stays `buffers[active]?.content ??
   file.data?.content` (buffer precedence — already safe); the new addition is
   `reconcileServer`, called from an effect when `file.data` changes: if a buffer exists and now
   equals fresh server content (e.g. our own patch was applied), drop it; else keep the buffer
   and show a non-blocking "file changed on disk" chip with a Monaco-diff "Review" action
   (buffer vs new server content) — never overwrite (hardens gap #16 for the IDE).
3. **Close guard**: `requestCloseTab` returns `needs-confirm` when dirty; `EditorPane` renders an
   inline confirm strip in the tab bar ("Discard unsaved changes to `x.py`? [Discard] [Keep]") —
   no browser `confirm()`, testable in Playwright.
4. **beforeunload**: one effect in `IdeWorkspace` registers `window.onbeforeunload` returning a
   string iff any buffer exists; removed on unmount. (Client-side route changes away from the IDE
   keep buffers in the store — tabs survive navigation within the SPA, which is the better UX;
   only hard unloads warn.)
5. **Reveal-at-line**: `EditorPane` keeps an `editorRef` via `onMount`; an effect consumes
   `pendingReveal` when `active === pendingReveal.path && file.data` →
   `revealLineInCenter(line)` + `setPosition` + clear.
6. **Propose flow fix** (`EditorPane.tsx:27-33`): `base_sha` comes from `buffers[active].baseSha`
   (the sha of the content the user actually edited, captured at first keystroke) instead of the
   possibly-refetched live sha; on success clear the buffer, invalidate `['patches']`, and show a
   chip "Patch proposed — review in chat" that sets `rightTab='chat'` and reveals the patch card
   (self-authored patches also appear as a synthetic "manual" entry at the bottom of the chat's
   Changes filter).

### D7. Workspace search (grep) panel (`features/ide/SearchPanel.tsx`, SHOULD)

Left rail gets Explorer / Search segmented tabs. Search input (350ms debounce, min 2 chars) →
`grepWorkspace(projectId, { query, limit: 100 })` (ASSUMED endpoint). Results grouped by file,
row = line number + highlighted preview; click → `openFileAtLine(path, line)`. 404 feature-detect
hides the Search tab entirely. Loading skeleton, "no matches", and `truncated: true` banner
("first 100 matches shown").

### D8. Theme + Monaco (`lib/ide/theme.ts` new, `lib/ide/monaco.tsx` modified)

`useResolvedTheme(): 'light' | 'dark'` — reads `document.documentElement.dataset.theme`
(the WS7 design-system ThemeProvider stamps `data-theme` on `<html>` per INNOVATION_IDEAS
WS7-1 §4; ASSUMED, see Cross-partition), subscribes via a `MutationObserver` on the
`data-theme` attribute, falls back to `matchMedia('(prefers-color-scheme: dark)')` when the
attribute is absent. No import of any design-system module → this partition builds standalone.
`monaco.tsx` exports gain a thin wrapper: `ThemedMonacoEditor` / `ThemedMonacoDiff` passing
`theme={resolved === 'dark' ? 'vs-dark' : 'vs'}` plus the shared default options object
(minimap off, fontSize 13, scrollBeyondLastLine false); existing raw exports remain for
non-owned consumers (paper feature imports `MonacoEditor` — untouched).

Styling: all new/modified IDE components use WS7 semantic token classes (`bg-surface`,
`border-border`, `text-text`, `text-muted`, `bg-accent`, `text-warn`, `text-success`,
`text-danger`). Fallback if WS7 is cut: implementer applies the reverse mapping table
(`bg-surface→bg-white`, `border-border→border-neutral-200`, `text-muted→text-neutral-400`,
`bg-accent→bg-neutral-900`, warn→amber-*, success→emerald-*, danger→red-*) — mechanical, listed
here so the build never references undefined utilities.

### D9. Layout (`features/ide/IdeWorkspace.tsx`, new)

Single component owning the whole IDE grid (so the un-owned `ide/page.tsx` shrinks to a
one-liner — see Cross-partition):

```
IdeWorkspace
 ├─ left rail (w-60): [Explorer|Search] tabs → FileTree / SearchPanel; GitTimelinePanel entry
 │  (StatusHeader always visible; expands the timeline into the right rail via rightTab='git')
 ├─ center: EditorPane (+ TerminalPanel unchanged below)
 └─ right rail (w-[26rem]): rightTab switch [Chat|Timeline] → CodingChat / GitTimelinePanel
 └─ ConnectionStatusPill (absolute, bottom-right): hidden when open; "reconnecting… (attempt n)"
    / "offline" from useProjectConnection
```

## API contract changes

This partition adds **no backend routes**. It consumes the following. Items marked **EXISTS**
are today's API (unchanged); **ASSUMED** items are requested from the coding-git partition with
these exact shapes (each has the fallback noted in Design).

EXISTS (unchanged consumption):
- `POST /projects/{id}/coding-agent/runs {message}` → `{agent_run_id, status, stream}` — fallback send path.
- `GET /projects/{id}/agents/runs`, `GET .../runs/{run_id}`, `GET .../runs/{run_id}/events?after_seq=` → `[{seq, event_type, payload_json, created_at}]` — replay source.
- `GET /projects/{id}/workspace/tree`, `GET /workspace/files?path=`.
- `GET/POST /projects/{id}/workspace/patches`, `GET /{patch_id}`, `POST /{patch_id}/apply`, `POST /{patch_id}/reject`.
- `GET /projects/{id}/git/status` → `{provider, branch, clean, ahead, behind, files:[{path, state}]}` (shape kept; data becomes real).

ASSUMED (coding-git to provide; consolidator reconciles):

1. Sessions —
   `POST /projects/{id}/coding-agent/sessions {title?}` → 201
   `{"id":"…","project_id":"…","title":"Add retry logic","status":"active","created_at":"…","updated_at":"…"}`;
   `GET /projects/{id}/coding-agent/sessions?limit&offset` → `Page<CodingSession>` newest-first;
   `GET /projects/{id}/coding-agent/sessions/{sid}/turns?limit&offset` → `Page<CodingTurn>` ascending, where
   `CodingTurn = {"agent_run_id":"…","session_id":"…","seq":3,"user_message":"…","status":"completed","output_text":"…"|null,"patch_id":"…"|null,"error":null|"…","token_usage":{"input_tokens":123},"created_at":"…"}`;
   `POST /projects/{id}/coding-agent/sessions/{sid}/messages {message}` → 201
   `{"agent_run_id":"…","session_id":"…","status":"queued","stream":"/ws?project_id=…"}`.
   Errors: 404 unknown session; 409 `{"error":{"code":"session_busy",…}}` when a run in the
   session is still live (client also guards). Fallback on 404/405 of the list route: implicit
   single session over `agent_runs` filtered `agent_type='coding'`.
2. Patch detail enrichment — `GET .../patches/{patch_id}` files gain
   `"base_content": "…"|null` (recorded base at proposal time; null for create) and typed
   `"hunks": [{"id":"…","header":"@@ -10,6 +10,8 @@","old_start":10,"old_lines":6,"new_start":10,"new_lines":8,"content":"@@-prefixed unified body"}]`.
   Fallback: absent → client-computed or whole-file rendering (D3.4).
3. Partial apply — `POST .../patches/{patch_id}/apply` optional body
   `{"selections":[{"file_id":"…","hunk_ids":["…","…"]}]}` (omit body ⇒ apply all, today's
   semantics); response `ApplyResult` gains `"applied_commit_sha":"…"|null` and
   `"skipped":[{"file_id":"…","hunk_ids":[…]}]`. Errors: 409 conflict (existing), 400/422
   `code:'unsupported'` if partial apply not implemented → UI hides checkboxes.
4. Git — `GET /projects/{id}/git/log?limit=50&offset=0` →
   `{"items":[{"sha":"…","short_sha":"a1b2c3d","message":"patch 9f2e: add retry\n\nAgent-Run: …","author_name":"researchos-bot","timestamp":"…","patch_id":"…"|null,"agent_run_id":"…"|null}],"total":123}`;
   `GET /projects/{id}/git/commits/{sha}/diff` →
   `{"sha":"…","parent_sha":"…"|null,"files":[{"path":"…","change_type":"modify","old_content":"…"|null,"new_content":"…"|null,"binary":false}]}`;
   `POST /projects/{id}/git/revert {"sha":"…"}` → 201 `{"revert_commit":{…GitCommit}}`;
   errors 409 `code:'git_dirty'` (tree not clean), 409 `code:'git_revert_conflict'`, 404 unknown
   sha. Fallback: log 404 ⇒ timeline empty-state mode.
5. Workspace grep — `GET /projects/{id}/workspace/grep?query=…&glob=…&regex=false&limit=100` →
   `{"matches":[{"path":"apps/api/x.py","line":42,"preview":"def foo(…):"}],"truncated":false}`.
   400 on invalid regex. Fallback: 404 ⇒ Search tab hidden.

## WS events

Consumed today (unchanged): `agent.run.started|token|tool_call.started|tool_call.completed|completed|failed|cancelled`.

Requested additions (producers = coding-git backend; type strings + payloads for the
shared-schemas consolidator — the client treats all of these as optional enhancements):

- `agent.run.token` payload gains optional `"seq": number` (monotone per run) → enables strict
  ordered/deduped token application (D2.1).
- `agent.run.text_snapshot` `{ "text": string, "through_seq": number }` — persisted every ~50
  tokens so replay can restore mid-run text (STRETCH on the backend; client support ships).
- `patch.created` `{ "patch_id": string, "agent_run_id": string | null, "summary": string, "file_count": number }` — resource_type `patch`.
- `patch.status_changed` `{ "patch_id": string, "status": "applied"|"rejected"|"conflict"|"partially_applied", "applied_commit_sha": string | null }` — resource_type `patch`.
- `git.commit.created` `{ "sha": string, "short_sha": string, "message": string, "patch_id": string | null, "agent_run_id": string | null }` — resource_type `project`.
- Client→server control frames (not envelopes; discriminated by `type` vs `event_type`):
  client sends `{"type":"ping","ts":<ms>}`; server replies `{"type":"pong","ts":<same>}`.
  Gateway must tolerate/ignore unknown client frames (it already never reads — reading+ignoring
  is the minimum viable change).

## DB changes

None. This workstream is frontend-only. (The ASSUMED backend contracts imply DB work —
`coding_sessions`, `agent_runs.session_id`, `patch_files.base_content`, per-hunk status,
`patch_proposals.applied_commit_sha` — all owned by coding-git; listed here only so the
migration consolidator can cross-check.)

## shared-schemas additions

For the dedicated consolidation agent (exact TS):

```ts
// events.ts
export const PATCH_EVENTS = ['patch.created', 'patch.status_changed'] as const;
export const GIT_EVENTS = ['git.commit.created'] as const;           // append both to EVENT_TYPES
export type ResourceType = /* existing */ | 'patch';
export interface AgentRunTokenPayload { delta: string; seq?: number }         // widen existing
export interface AgentRunTextSnapshotPayload { text: string; through_seq: number }
export interface PatchCreatedPayload { patch_id: string; agent_run_id: string | null; summary: string; file_count: number }
export interface PatchStatusChangedPayload { patch_id: string; status: 'applied'|'rejected'|'conflict'|'partially_applied'; applied_commit_sha: string | null }
export interface GitCommitCreatedPayload { sha: string; short_sha: string; message: string; patch_id: string | null; agent_run_id: string | null }
// control-frame contract (new file or events.ts):
export interface WsPing { type: 'ping'; ts: number }
export interface WsPong { type: 'pong'; ts: number }
```

Until consolidation lands, this partition types these locally in `lib/websocket/types.ts` with
string literals (no compile-time dependency on the schemas package changing).

## New dependencies

None. The line diff is hand-rolled (D4); hunk rendering is plain HTML/CSS; Monaco, TanStack
Query, Zustand already present.

## File-by-file plan

`apps/web/features/ide/`
- `CodingAssistant.tsx` — **deleted** (superseded by chat; the 5×setTimeout pattern dies here).
- `PatchReviewPanel.tsx` — **deleted** (review lives in DiffCards; the 5s poll dies here).
- `PatchDiff.tsx` — **deleted** (live-file diff bug dies here).
- `EditorPane.tsx` — **modified**: new store wiring, buffer/dirty model, inline close-confirm
  strip, reveal-at-line effect, propose fix (base_sha from buffer fork, clear on success, chip →
  chat), on-disk-change chip, ThemedMonacoEditor, token classes, error/empty states.
- `FileTree.tsx` — **modified**: token classes, EmptyState/error treatment, `requestCloseTab`
  awareness none (unchanged open flow), minor: active-file highlight via store.
- `GitStatusPanel.tsx` — **rewritten** into a thin `StatusHeader` re-export used by
  `GitTimelinePanel` (keeps the export name so nothing else breaks).
- `TerminalPanel.tsx` — **unchanged** (out of scope, P3-D11 stands).
- **new** `IdeWorkspace.tsx` (layout, rightTab switch, beforeunload, connection pill mount).
- **new** `SearchPanel.tsx` (D7).
- **new** `ConnectionStatusPill.tsx`.
- **new** `chat/CodingChat.tsx`, `chat/SessionBar.tsx`, `chat/ChatTurn.tsx`,
  `chat/IdeToolCallChip.tsx`, `chat/Composer.tsx`.
- **new** `chat/DiffCard.tsx`, `chat/FileDiffSection.tsx`, `chat/HunkView.tsx`.
- **new** `git/GitTimelinePanel.tsx`, `git/CommitDiffViewer.tsx`, `git/RevertRow.tsx`.

`apps/web/lib/websocket/`
- `client.ts` — **rewritten** (D1: manager, backoff+jitter, heartbeat probe, dedupe, control
  frames, status). Keeps `projectWsUrl` + `connectProjectEvents` compat exports.
- `useProjectAgentEvents.ts` — **rewritten** (D2) preserving exported names/shapes
  (`useProjectAgentEvents`, `LiveRun`, `LiveToolCall`); adds `useProjectConnection`.
- **new** `types.ts` (control frames, local event literals, SocketStatus).

`apps/web/lib/api/`
- `codingAgent.ts` — **modified**: sessions/turns/sendMessage clients + `CodingSession`,
  `CodingTurn` types + kept `createCodingRun`; local `CodingAgentRun` type widening
  (`agent_type: 'coding'`, `output_json.patch_id?: string`).
- `patches.ts` — **modified**: `PatchHunk` typed, `PatchFile.base_content?: string | null`,
  `applyPatch(projectId, patchId, selections?)`, `ApplyResult.applied_commit_sha?`,
  `.skipped?`.
- `git.ts` — **modified**: `GitCommit`, `getGitLog`, `CommitDiff`, `getCommitDiff`,
  `revertCommit`; `getGitStatus` unchanged.
- `workspace.ts` — **modified**: `grepWorkspace` + `GrepMatch`/`GrepResponse` types; existing
  exports untouched.

`apps/web/lib/ide/`
- `monaco.tsx` — **modified** (D8 themed wrappers; raw exports preserved).
- `language.ts` — **modified** (add `tex→latex? no — keep IDE scope:` add `rs, go, c, h, cpp,
  sql, xml, svg→xml, lock→plaintext`; leave latex to WS4's partition).
- **new** `store.ts` (D6 IdeState v2 — replaces un-owned `lib/store/ide.ts`).
- **new** `diff.ts` (D4).
- **new** `theme.ts` (D8 `useResolvedTheme`).
- **new** `useCodingSessions.ts` (D3.1 feature detection + fallback mapping).

## Cross-partition requests

1. **`apps/web/app/(workspace)/projects/[projectId]/ide/page.tsx`** (layout partition): replace
   the body so the page renders exactly:
   `import { IdeWorkspace } from '@/features/ide/IdeWorkspace';` … `return <IdeWorkspace projectId={projectId} />;`
   (keep the `use(params)` unwrap). All other imports removed.
2. **`apps/web/lib/store/ide.ts`**: delete the file once this spec lands (its only importers,
   `EditorPane.tsx`/`FileTree.tsx`, move to `@/lib/ide/store`). If deletion is awkward, leaving
   it dead is acceptable — nothing will import it.
3. **`apps/web/lib/api/agents.ts`** (agents/research partition): widen
   `export type AgentType = 'research' | 'critic' | 'coding' | 'latex' | 'experiment';` so the
   fallback filter needs no cast. Non-blocking (local cast used meanwhile).
4. **coding-git backend spec**: implement the five ASSUMED contract blocks (sessions, patch
   detail `base_content`+typed hunks, partial-apply body + `applied_commit_sha`, git
   log/diff/revert, workspace grep) and the WS events + ping/pong echo listed above, with those
   exact routes/shapes. Also: persist coarse events for coding runs exactly as for research runs
   (already true today) so replay works.
5. **design-system (WS7) spec**: confirm the ThemeProvider stamps `data-theme="light"|"dark"` on
   `<html>` (resolved value, not `"system"`), and that the semantic token utility classes in D8
   exist in `tailwind.config`. No module import is taken; attribute + classes only.
6. **e2e** (test-infra partition / consolidator): add `apps/web/e2e/ide.spec.ts` with the
   scenarios in Test plan (file content provided by this partition's implementer; it lives
   outside the strict ownership glob).

## MUST / SHOULD / STRETCH

MUST (core, no backend assumption beyond what exists today):
- D1 socket manager (shared socket, backoff+jitter, dedupe, status, reopen signal; heartbeat
  probe that stays silent against the current gateway).
- D2 reducer rewrite: idempotent folds, trackRun catch-up replay, reopen replay via existing
  events endpoint, bounded run map, unchanged public API (research/paper/experiments surfaces
  keep compiling untouched).
- D3 CodingChat in fallback mode at minimum (implicit session over coding agent_runs), streaming
  bubbles, tool chips, Composer; zero polling/timers.
- D3.4/D4 DiffCard with per-file collapsible client-computed or hunk-based diffs (never
  live-file), Apply-all / Reject-all against the existing endpoints, in-place status pill,
  conflict rendering.
- D6 store v2 + editor fixes: dirty model, close confirm, beforeunload, reconcileServer,
  propose fix, reveal-at-line plumbing.
- D9 IdeWorkspace layout + deletion of the three legacy components; empty/loading/error states
  everywhere per D8 styling rules.
- D5 GitTimelinePanel with graceful 404 empty-state (renders fully once backend lands).

SHOULD (needs ASSUMED backend, all feature-detected):
- Real sessions UI (SessionBar, session create/switch).
- Per-hunk checkboxes + partial apply call + `Apply selected (k/n)`.
- Git log/commit-diff/revert flows live; commit↔turn↔patch chips both directions.
- D7 SearchPanel (grep) + open-at-line from results.
- Heartbeat active mode (pong-capable), `patch.*`/`git.*` event-driven invalidation.
- ConnectionStatusPill; language map additions.

STRETCH:
- `agent.run.text_snapshot` replay-of-text support (client side lands with D2; inert until
  backend emits).
- Cancel-run button on a live turn (`POST /agents/runs/{id}/cancel` exists).
- Right-rail / bottom-panel drag resize (store fields exist; setters + pointer handlers).
- Virtualized CommitList beyond 200 commits.

## Acceptance criteria (verifiable via local gates + code reading)

1. `pnpm tsc --noEmit` and `pnpm next build` pass in `apps/web`; `grep -r "setTimeout" apps/web/features/ide` returns no polling-invalidation hits; `grep -rn "refetchInterval" apps/web/features/ide` empty.
2. `CodingAssistant.tsx`, `PatchReviewPanel.tsx`, `PatchDiff.tsx` no longer exist; no file
   outside the partition imports them (`grep -rn "PatchReviewPanel\|CodingAssistant\|features/ide/PatchDiff"` → only `ide/page.tsx` until cross-partition request 1 lands).
3. `lib/websocket/client.ts` contains exactly one `new WebSocket(` site; reconnect delay
   expression includes both an exponential term and a random factor; an LRU dedupe over
   `event_id` exists; parse failures log a warning.
4. `useProjectAgentEvents` exports are shape-identical (verified by `tsc` across the untouched
   `ResearchChat`/`PaperAssistant`/`AnalysisPanel` imports); `trackRun` performs an events fetch;
   a `reopen` path calls `getAgentRunEvents` with `after_seq = lastCoarseSeq`; token fold
   contains a `seq >` guard; tool-call fold is an upsert by seq.
5. `DiffCard` renders from `base_content`/server hunks/`new_content` only — no query for the
   live file path exists in `chat/`.
6. `diff.ts` is dependency-free and pure (no imports besides types); `groupHunks` default
   context is 3.
7. Closing a dirty tab renders the confirm strip (code path: `requestCloseTab` →
   `'needs-confirm'`); `window.onbeforeunload` registered iff buffers non-empty; `setBuffer`
   deletes the buffer on content equality; `reconcileServer` never writes server content into an
   existing differing buffer.
8. Every ASSUMED endpoint call site handles 404/405/422 with the documented fallback (code
   review: `useCodingSessions`, `DiffCard` selections path, `GitTimelinePanel`, `SearchPanel`).
9. All new components use token classes (or the documented fallback set) and each data surface
   has explicit loading (skeleton), empty (message + primary action), and error (message +
   retry) branches.
10. Playwright specs from the Test plan are authored and pass in CI against the seeded stack
    with the mock LLM (mock coding agent already produces a deterministic patch — no mock
    extension needed by this workstream).

## Test plan (CI-run; no external network)

Playwright (`apps/web/e2e/ide.spec.ts`, via cross-partition request 6; demo seed + mock LLM):
1. **chat-to-diff happy path**: open `/projects/{id}/ide`, type a request, submit → user bubble
   appears immediately; await completed turn; assert a DiffCard rendered with ≥1
   `FileDiffSection` and +/− stats present; click Apply-all → status pill becomes `applied`;
   file tree invalidation observed (tree request refires).
2. **conflict rendering**: apply the same patch twice (second apply → conflict) → red conflict
   panel with per-path reason inside the card; card still visible in history.
3. **dirty guard**: open a file, type, click tab × → confirm strip appears; Keep preserves
   buffer; Discard closes; `beforeunload` handler present (`page.evaluate(() => !!window.onbeforeunload)`).
4. **reconnect**: `page.evaluate` closes the underlying socket (test hook: manager exposes
   `__rosSockets` in `process.env.NODE_ENV !== 'production'` guard); assert pill shows
   reconnecting then disappears; submit a new chat message post-reconnect and receive stream.
5. **git timeline**: if `GET /git/log` 200s in the environment, assert commit rows render and a
   patch commit's chat chip scrolls to/highlights the turn; else assert the empty state (both
   branches coded so the spec passes before and after coding-git lands).
6. **fallback mode**: with sessions endpoint absent (current backend), SessionBar hidden, chat
   history built from coding runs.

pytest: none owned here (frontend-only partition; backend contract tests belong to coding-git;
`apps/api/tests/test_ws_contract.py` continues to pin the envelope, and the shared-schemas
consolidator extends it for the new event strings).

## Explicitly out of scope

- Terminal execution (P3-D11 stands), file create/rename/delete/upload in the tree, Monaco
  offline bundling (P3-D13 stands), LaTeX editor surfaces (WS4 partition), i18n of IDE strings
  (IDE is English-only today; dictionaries are outside the partition), RunInspector drawer
  (WS7-3, other partition), any backend code, alembic migrations, shared-schemas edits (listed
  for the consolidator only), repo-map outline panel (WS2-5 backend-first).
- **Superseded prior decisions** (flagged for the record, implemented backend-side by
  coding-git): P3-D4 "whole-file apply, hunks display-only" → per-hunk selective apply UI here;
  P3-D10 "git read-only stub" → log/diff/revert UI here (revert stays non-destructive —
  inverse commits only, honoring the no-destructive-git rule). This spec supersedes nothing
  else in PHASE1/PHASE3.
