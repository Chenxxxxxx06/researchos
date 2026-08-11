# ResearchOS requirements audit

Audit date: 2026-08-11
Source: `科学文献研究智能体：从综述到实验设计 (1).docx`

This report distinguishes persisted, executable functionality from UI-only or externally blocked
functionality. A page being visible is not counted as completion.

## Teacher DOCX mapping

| Requirement | Status | Evidence in this project | Remaining boundary |
| --- | --- | --- | --- |
| Structured paper knowledge base | Partial | Persisted papers, sections, chunks, reading cards, notes, citations, summaries and provenance | Zotero attachments/collection hierarchy are not yet imported as full text automatically |
| Reading assistant | Implemented | Section ingestion, structured reading cards, research question, method flow, strengths, limitations and reproducibility fields | Output quality requires an active real LLM; the UI now blocks Mock output |
| Literature search | Implemented | Federated paper search, library import, Zotero sync and source provenance | External providers remain subject to their uptime/rate limits |
| Scientific SQL Agent | Implemented | Project-scoped dataset sources, query validation, persisted query results and SQL analysis workspace | Requires a configured dataset source |
| Topic clustering | Implemented | Persisted mission topic clusters and mission literature workflow | Quality depends on the available library |
| Review outline and drafting | Implemented | Mission review document, structured sections, versioning and review-section Agent | Real generation requires a tested model connection |
| Experiment planning and variables | Implemented | Evidence-bound experiment-plan Agent, variables, baselines, metrics, matrix and decision/stop rules | Real generation requires a tested model connection |
| Voice assistant | Partial | Browser streaming speech capture plus server-side audio upload/transcription path | Uploaded audio requires an active OpenAI-compatible config named `asr`; no offline ASR bundle is shipped |
| Citation organizer | Implemented | Citation organizer Agent, audit records, citation insertion and BibTeX workspace | Citation correctness still requires human review |
| Research frontend | Implemented | Topic/mission, paper list, reading, review, experiment plan, history and project overview pages | — |
| Backend management | Implemented | Organization, project, researcher, paper, plan and note summary backed by persisted objects | Destructive bulk administration is intentionally not exposed |
| End-to-end topic → literature → review → plan | Implemented | Durable mission steps with approval gates and timeline | Real Agent generations require an active model |

## Requested product changes

| Requested change | Status | What is real now |
| --- | --- | --- |
| Zotero connection | Verified live | Credentials and user permissions were verified against Zotero; 86 records were created and 8 DOI-linked in the live sync. Credentials are encrypted at rest and masked in API/UI responses. |
| Research Inbox | Implemented | PDF, DOCX, Markdown, text/data formats and audio are handled by a server upload endpoint; originals are persisted and prompts label facts, inferences, actions and evidence gaps. Text extraction works without an LLM; analysis is locked until a real model is configured. |
| Local AI IDE | Implemented | Project owners can mount an existing absolute local folder, switch among recent folders or reset to isolated managed storage. The real tree/read/save/grep, terminal, reviewed Agent patches and Git history all follow the active folder, with SHA concurrency and path guards. |
| SSH IDE | Implemented, connection pending | Encrypted password/private-key profiles, mandatory `known_hosts`, SFTP tree/read/save, symlink/root guards, command allowlist, timeouts and persisted execution audits. API and safety tests pass; no real lab SSH host was provided for a live connection test. |
| Experiment mentor | Implemented, generation pending | A first-party `research-mentor` Skill reads project state, selected runs, recorded metrics, logs and commit metadata, then requests a falsifiable next-run plan. Per-run Skill selection prevents unrelated installed Skills from contaminating the prompt. |
| Simulated reviewer | Implemented, generation pending | `reviewer-challenger` Skill can load the paper workspace, research ideas and completed-run metrics into an evidence-bound review and prioritized revision plan. It explicitly avoids acceptance prediction. |
| Release studio | Implemented, generation pending | One auto-built Story Pack feeds three Coding Agent targets: `page/` plus GitHub Pages workflow, root `README.md`, and `poster/`. Outputs are pending patches with file-level review and explicit apply. Generation is locked without a real model. |
| Paper workspace | Partial | Versioned LaTeX editing, citations, figures, tracked Agent suggestions, conflict merge and structural preview are real. Compilation is still a safe structural parser, not an isolated TeX-to-PDF engine. |
| Remove Agent Collaboration and DDL | Implemented | Removed from navigation and command palette; legacy URLs redirect to project overview. |
| Merge Settings and Management | Implemented | One Management Center now contains persisted assets, appearance/language and encrypted model configuration. The old settings URL redirects to its system tab. |
| UI redesign | Implemented | Navigation is reduced to five product phases, the overview is database-driven, and the visual system uses a restrained research-green editorial language with honest status boundaries. |

## Verification performed

- Live Zotero API permission check and UI sync: passed.
- Zotero persisted-secret inspection: encrypted, not plaintext.
- Browser smoke across core pages and legacy redirects: 1 passed.
- Frontend TypeScript and lint: passed.
- Frontend production build: passed.
- Core Skill, Inbox and secret tests: 15 passed.
- SSH profile encryption and SSH path/command safety tests: 3 passed.
- Selectable local workspace plus affected filesystem, patch, Git and Coding Agent regression tests: 51 passed, 1 platform-specific symlink test skipped.
- Earlier backend focused suite with the correct test database/Redis: 35 passed, 1 skipped.
- Full backend suite was started but remained silent for several minutes; it was stopped and is not reported as passed.

## External gates before public release

1. Add and test a real project LLM configuration; add a separate `asr` configuration for uploaded audio.
2. Test one real SSH host using its verified `known_hosts` entry and a disposable remote project directory.
3. Generate and review all three release patches with the real model, then apply them in the AI IDE.
4. Add a GitHub remote/token outside the application and push the generated Pages workflow.
5. Add an isolated TeX compiler service if PDF compilation is required inside the product.
6. Extend Zotero sync to collections and attachment/full-text ingestion if Zotero is expected to be the sole paper-ingestion route.
