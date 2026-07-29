# ResearchOS Project Memory

This repository builds a scientific Agent Harness: models reason, tools act,
ResearchOS controls context, permissions, provenance, experiments, and human
approval.

## Persistent engineering rules

- Never fabricate papers, citations, datasets, baselines, metrics, experiments,
  reviewer opinions, or release claims.
- Every important scientific claim should eventually resolve to
  `Claim → Evidence → Run → Artifact → Commit`.
- Coding agents propose reviewable patches. Do not silently overwrite unrelated
  user changes.
- Real execution is local-only until an isolated runner exists. Remote SSH,
  arbitrary shell, LaTeX compilation, and third-party code require explicit
  sandbox policies.
- A coordinator dispatches work; specialist agents own one artifact type and
  return structured handoffs.

## Human gates

- Scope: research question, success metric, budget, and target venue.
- Evidence: citations, experiment results, statistics, and reproducibility.
- Release: final paper, code, website, poster, and public claims.

## Context compaction

Preserve decisions, rejected hypotheses and reasons, verified claims and
sources, experiment lineage, open risks, artifact ownership, and the next
executable task. Raw logs remain external artifacts and should not be copied
into long-term memory.
