# ResearchOS — Phase 3 Architecture Decisions

Status: **Accepted**.
Scope: Phase 3 — AI IDE Workspace MVP (local controlled workspace + reviewable
patch proposals). No real SSH, no arbitrary shell, no unreviewed writes.

---

## 1. Decision Log

| # | Topic | Decision | Notes |
|---|-------|----------|-------|
| P3-D1 | Workspace root | Each project maps to `<WORKSPACE_ROOT>/<project_id>`, created empty on first access. | `project_workspace_settings` table deferred; root is derived from config. |
| P3-D2 | Source of truth | The **filesystem** is the source of truth for file content and the tree. The DB stores only patch metadata and agent runs. | Avoids DB/FS drift; the tree/content are read live from the FS. |
| P3-D3 | Drift avoidance | Patches store `path` + `base_sha` + proposed `new_content`. Apply **re-reads the FS, compares the current sha**, and only then writes. | Mismatch → `conflict`, nothing written. |
| P3-D4 | Apply granularity | **Whole-file replacement guarded by `base_sha`** (optimistic concurrency). `patch_hunks` are **display-only**; no partial hunk apply. | Simple and safe for MVP. |
| P3-D5 | AI cannot write | The Coding Agent only **proposes** a pending patch; it never writes files. Applying a patch is a separate, user-initiated, CSRF-protected, role-checked action. | |
| P3-D6 | Coding runs | Reuse `agent_runs` with `agent_type = coding`; the run's finalize creates a pending `patch_proposal`. | Read-only tools only, via the Tool Broker. |
| P3-D7 | Path guard | Every path is resolved (`Path.resolve`, follows symlinks) and must be inside the resolved workspace root. Absolute paths, `..`, and symlink escapes are rejected. | See `common/paths.py`. |
| P3-D8 | Deny-list | Sensitive files are hidden from the tree and return **403** on read/patch: `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`, `id_dsa*`, `*credential*`, `*.secret`, and the `.git/` directory. | |
| P3-D9 | Permissions | read (tree/file/git) = viewer+; create patch / coding-agent run = researcher+; **apply/reject = researcher+** (viewer cannot apply). | Enforced in the service layer. |
| P3-D10 | Git | **Read-only abstraction only.** Default `StubGitStatusProvider` returns a clean/empty status. A `ReadOnlyGitStatusProvider` interface is reserved but not implemented. No destructive git operations. | |
| P3-D11 | Terminal | UI/log shell only. **No real command execution.** | |
| P3-D12 | SSH runtime | Interface + permission model only (`runtime/ssh/interface.py`). **No connection.** | Phase 4. |
| P3-D13 | Monaco | Loaded in the browser via the `@monaco-editor/react` loader (CDN at runtime). The Next build does not bundle Monaco. | Editor renders client-side only (`ssr: false`). |
| P3-D14 | FS I/O | Synchronous file I/O for MVP (small files), invoked from async services. | Acceptable; revisit with `to_thread` if needed. |

## 2. Database

New tables: `patch_proposals`, `patch_files`, `patch_hunks`. New enums:
`patch_status` (pending/applied/rejected/conflict), `patch_change_type`
(create/modify/delete). `agent_type` gains `coding` via
`ALTER TYPE ... ADD VALUE` (irreversible in downgrade — documented).

**In DB**: patch proposals/files/hunks, coding agent runs (`agent_runs`).
**Not in DB (FS/live or client-only)**: file content, file tree, opened tabs,
editor buffers, panel sizes.

## 3. Non-goals

Real SSH execution, arbitrary shell, unreviewed writes, full git, experiments,
LaTeX, skills runtime, collaborative editing, VSCode extension compatibility.

## 4. Known limitations

- Apply checks all shas then writes; a mid-write OS failure could leave a
  partial apply (small risk for small files; revisit with temp-write+rename).
- Monaco requires browser internet for the CDN loader.
- Git status is a stub; no real VCS state yet.
