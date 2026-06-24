# ResearchOS Skill Builder

## What is a Skill?

A ResearchOS **Skill is not just a prompt**. It is a packaged research capability
described by a **manifest**. A skill bundles:

- **prompt template** — the instruction the agent uses;
- **workflow** — ordered steps describing how the skill works;
- **tool permissions** — an explicit, allow-listed declaration of which platform
  tools the skill may request (e.g. `paper.search`, `library.list`);
- **config schema** — a small JSON schema of user-configurable options;
- **modules** — which product surfaces it applies to (Research, IDE,
  Experiments, Paper);
- metadata — slug, name, version, description, category, author, visibility.

## Skill Manifest structure

```json
{
  "slug": "my-nature-skill",
  "name": "My Nature Skill",
  "version": "1.0.0",
  "description": "Rewrites prose in a Nature style.",
  "author": "custom",
  "category": "writing",
  "modules": ["paper"],
  "prompt_template": "Rewrite the selection in a concise Nature style…",
  "workflow": ["Analyze selection", "Rewrite", "Tighten claims"],
  "tool_permissions": [],
  "config_schema": { "tone": { "type": "string", "default": "formal" } }
}
```

## First-party vs custom skills

| | First-party | Custom |
|---|---|---|
| Owner | Global (no project) | A specific project |
| Source | Seeded by the platform | Created in the Skill Builder UI |
| Visibility | `first_party` | `custom` |
| Examples | Nature Writing, CVPR Reviewer, VLM Evaluation, Experiment Analysis, LaTeX Polish | Anything a user builds |

Both kinds are installed and enabled per project through the same APIs.

## What the MVP supports

- Browse a marketplace catalog (first-party + this project's custom skills).
- View skill detail: modules, tool permissions, workflow, prompt template.
- Install / enable / disable a skill per project.
- **Skill Builder**: create and edit a custom skill — basic info, applicable
  modules, prompt template, workflow steps, tool permissions, config schema —
  with **manifest preview**, **validation**, and **save & install**.

## What the MVP does NOT support (security boundaries)

- **No arbitrary code execution.** A custom skill stores only a manifest, prompt
  template, workflow description, and permission declarations.
- No shell commands, no dynamic import of third-party Python/JS.
- Declaring a tool permission does **not** grant execution. Tools are only ever
  run through the platform **Tool Broker**, which enforces project membership and
  records every call. Tool permissions must be chosen from a fixed allow-list
  (`GET /projects/{id}/skills/allowed-tools`).
- Third-party (non-first-party, non-custom) marketplace publishing, signing, and
  sandboxed runtime injection are out of scope.

## How to create a "Nature Writing" style skill

1. Open **Skill Builder** (`/projects/{projectId}/skills/builder`).
2. Fill **basic info**: slug `nature-style`, name `Nature Style`, version `1.0.0`,
   category `writing`.
3. Select the **Paper** module.
4. Write a **prompt template**, e.g. *"Rewrite the selected text in the concise,
   authoritative style of a Nature article; preserve all factual claims and
   citations."*
5. Add **workflow** steps (one per line): `Analyze selection`, `Rewrite for
   clarity`, `Tighten claims`.
6. Leave **tool permissions** empty (writing needs no tools) or pick from the
   allow-list.
7. Click **Validate**, then **Save & install**.

## How to enable a skill in the Paper Workspace

1. Open **Skills** (`/projects/{projectId}/skills`).
2. Find the skill card and click **Install**, then **Enable**.
3. The skill is now enabled for the project and applies to its declared modules
   (here, **Paper**). The Paper Workspace assistant runs through the agent
   service/runtime layer, where enabled skills are injected (interface reserved;
   full runtime injection lands in a later phase).

## Future: real runtime injection

The current MVP keeps the **interface** for skill runtime injection but does not
execute skill-provided logic. A later phase will:

- Load skill prompt fragments + workflow into agent runs through the skill
  runtime, gated by the declared tool permissions and the Tool Broker.
- Add signed third-party packages, static scanning, sandboxed execution, network
  egress controls, and version pinning/rollback.
