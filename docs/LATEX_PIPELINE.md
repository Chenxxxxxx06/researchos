# ResearchOS LaTeX Pipeline

## 1. Purpose

The LaTeX pipeline supports real-time paper writing with AI assistance, multi-file LaTeX projects, BibTeX, compile logs, PDF preview, and experiment-to-paper asset insertion.

## 2. Components

- LaTeX project manager
- Monaco LaTeX editor
- Citation and BibTeX manager
- Compile worker
- PDF artifact store
- Compile log parser
- Latex Agent
- Paper asset inserter

## 3. Compile Flow

1. User edits a LaTeX file.
2. Frontend saves document version.
3. User or autosave triggers compile.
4. Backend creates compile job.
5. Worker copies project files into isolated container workspace.
6. Worker runs configured engine, such as `latexmk`.
7. Worker uploads PDF and logs to object storage.
8. Backend updates compile job.
9. WebSocket emits status and PDF URL.

## 4. Isolation

LaTeX compilation must be sandboxed because projects can contain unsafe commands.

Controls:

- Disable shell escape by default.
- Run compile in container with CPU/memory/time limits.
- No network access during compile by default.
- Clean workspace after compile.
- Store only expected artifacts.

## 5. File Model

Each LaTeX project has:

- Main file path
- Supporting `.tex` files
- `.bib` files
- Figure assets
- Style/class files
- Compile settings
- Version history

## 6. Citation Flow

1. User imports papers into project library.
2. System generates or imports BibTeX entries.
3. Latex Agent suggests citations from actual library records.
4. User inserts citation.
5. BibTeX file updates.
6. Compile validates reference.

The system must not invent citations.

## 7. AI Writing Flow

Latex Agent can:

- Draft sections from outline and source papers.
- Rewrite selected text.
- Fix compile errors.
- Insert experiment result summaries.
- Generate captions from artifacts.
- Draft reviewer responses.

All generated claims should be traceable to cited papers, experiment runs, or user-provided assumptions.

## 8. Experiment-to-Paper Sync

Experiment runs can produce paper asset candidates:

- Table rows
- Figure files
- Captions
- Result section snippets
- Ablation summaries

The user reviews candidates before insertion. The inserted content stores links back to experiment runs and artifacts.

## 9. Future Extensions

- Collaborative editing with CRDTs.
- PDF source sync.
- Commenting and review mode.
- Venue template marketplace.
- Overleaf import/export.
- Git-backed paper projects.
