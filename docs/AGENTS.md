# ResearchOS Agent System

## 1. Agent Principles

- Agents are specialized workers, not magic global assistants.
- Every agent run has explicit input, context, tools, permissions, trace, and output.
- Agents write important state through domain services, not directly into database tables.
- Risky actions require approval gates.
- Agents should cite sources, files, runs, or assumptions.

## 2. Shared Agent Runtime

Each agent receives:

- User request
- Project context pack
- Skill context
- Memory retrieval results
- Available tools
- Permission policy
- Output schema
- Trace writer

Each agent produces:

- Structured result
- Natural language summary
- Tool-call trace
- Memory write candidates
- Domain events
- Follow-up recommendations

## 3. Planner Agent

### Purpose

Break user intent into executable research steps and route work to specialized agents.

### Inputs

- User message
- Project state
- Active files, papers, experiments, or documents
- Installed/enabled skills

### Outputs

- Task plan
- Agent routing decision
- Tool permission requirements
- Human approval requirements

### Tools

- Project context retriever
- Memory graph query
- Skill registry
- Task creation
- Agent dispatcher

### Workflow

1. Classify request.
2. Retrieve relevant project context.
3. Select skills and tools.
4. Decompose into steps.
5. Dispatch specialized agents.
6. Merge results and produce final response.

## 4. Research Agent

### Purpose

Discover, retrieve, summarize, and organize research sources.

### Inputs

- Research topic or question
- Existing paper library
- Novelty target
- Venue or date constraints

### Outputs

- Ranked papers
- Summaries
- Related work clusters
- Dataset and baseline candidates
- Source-backed answer

### Tools

- arXiv search
- Semantic Scholar or OpenAlex search
- GitHub search
- PDF ingestion
- Citation graph lookup
- Vector search
- Paper library writer

### Memory

Reads papers, ideas, notes, previous related work, and project goals. Writes paper summaries, clusters, and source edges.

## 5. Critic Agent

### Purpose

Evaluate novelty, weaknesses, missing baselines, dataset risks, reproducibility, and reviewer objections.

### Inputs

- Idea, method, experiment plan, or paper section
- Related papers
- Target venue
- Current experiment evidence

### Outputs

- Novelty score with caveats
- Weakness list
- Missing baseline list
- Dataset concerns
- Reproducibility checklist
- Suggested fixes

### Tools

- Paper search
- Memory graph query
- Baseline registry
- Dataset registry
- Experiment comparison

### Workflow

1. Restate claim.
2. Compare with similar work.
3. Identify unsupported assumptions.
4. Check baseline and dataset coverage.
5. Produce concrete next actions.

## 6. Coding Agent

### Purpose

Assist code understanding, editing, debugging, and experiment scaffolding inside the IDE workspace.

### Inputs

- User request
- Selected files
- Repository context
- Experiment objective
- Runtime constraints

### Outputs

- Proposed patch
- Explanation
- Test or run command
- Risk notes

### Tools

- File read
- File search
- Patch generation
- Terminal command proposal
- Git diff
- Test runner
- Remote runtime launch request

### Guardrails

- Must request approval before destructive operations, credential access, or remote execution.
- Must produce diffs before applying non-trivial edits.
- Must link code changes to experiment or paper goals where relevant.

## 7. Latex Agent

### Purpose

Support academic writing, LaTeX editing, citation insertion, compile-error repair, and reviewer response.

### Inputs

- Paper outline
- Selected text or LaTeX file
- Citation library
- Experiment results
- Target venue

### Outputs

- Section draft
- Rewrite
- Citation suggestions
- Compile fix
- Reviewer response draft

### Tools

- Document file read/write
- Citation search
- BibTeX manager
- Compile log parser
- PDF reference locator
- Experiment asset inserter

### Guardrails

- Must not invent citations.
- Must mark speculative claims.
- Must preserve mathematical notation unless explicitly asked to rewrite it.

## 8. Experiment Agent

### Purpose

Plan experiments, monitor runs, analyze metrics, compare results, and generate paper-ready assets.

### Inputs

- Experiment goal
- Run metrics
- Logs
- Artifacts
- Baseline expectations

### Outputs

- Run summary
- Failure diagnosis
- Comparison analysis
- Table data
- Figure recommendation
- Caption draft
- Next experiment suggestions

### Tools

- Experiment run query
- Metrics query
- Log search
- Artifact browser
- Remote runtime status
- Paper asset generator

## 9. Agent Run Trace

Every run stores:

- Agent type and version
- Triggering user and project
- Input payload
- Retrieved context IDs
- Skill IDs
- Tool calls and arguments
- Approval decisions
- Output
- Token/cost metrics
- Error state

## 10. Multi-Agent Orchestration

Use LangGraph or equivalent state graph for:

- Planner-driven routing
- Parallel paper search and critique
- Tool approval checkpoints
- Retry and fallback states
- Human-in-the-loop decisions
- Final synthesis

The platform should support synchronous chat-like runs and background runs that continue after the user leaves the page.
