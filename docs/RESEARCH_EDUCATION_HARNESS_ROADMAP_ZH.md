# 科研教育 Harness：后续链路、Skill、Prompt 与框架设计

## 1. 为什么它不仅是科研自动化

ResearchOS 可以同时成为：

1. 科研生产 Harness：帮助研究者完成调研、实现、实验、论文和发布。
2. 科研教育 Harness：让学生看到每个结论、决策和修改是如何形成的。
3. 实验室知识 Harness：把人员更替时最容易丢失的隐性知识变成可审计资产。

教育目标不能只是“帮助学生更快得到答案”。系统应该训练：

- 如何提出可证伪的研究问题；
- 如何判断文献证据的强弱；
- 如何选择 baseline、benchmark、metric 和 ablation；
- 如何区分模型建议、论文陈述和实验事实；
- 如何分析失败结果；
- 如何写出可复现、不过度主张的论文；
- 如何回复 Reviewer 并承担学术责任。

## 2. 端到端链路

```text
一句研究目标
  ↓
Research Scoping
  ├── 问题、范围、目标 venue
  ├── 时间/算力/数据约束
  └── 成功指标 → 人工 Scope Gate
  ↓
Literature & Evidence
  ├── Zotero-first
  ├── 外部检索
  ├── Claim/Evidence 抽取
  └── 文献覆盖与引用完整性检查
  ↓
Idea & Hypothesis
  ├── research gap
  ├── falsifiable hypothesis
  ├── novelty challenge
  └── feasibility/risk
  ↓
Implementation
  ├── baseline reproduction
  ├── reviewable code patches
  ├── dataset/model contracts
  └── environment lock
  ↓
Experiment DAG
  ├── smoke test
  ├── baseline
  ├── main experiment
  ├── ablation
  ├── robustness/error analysis
  └── reproducibility rerun
  ↓
Evidence Gate
  ├── metric/artifact/commit binding
  ├── statistical checks
  └── human verification
  ↓
Paper
  ├── claims-first outline
  ├── result anchors
  ├── citation audit
  ├── figures/tables
  └── venue formatting
  ↓
Reviewer Arena
  ├── simulated reviews
  ├── response matrix
  └── revision loop
  ↓
Release Gate
  ├── paper/code/license/privacy
  ├── website/README/poster
  └── final human approval
```

## 3. Agent 角色

| 角色 | 主要输出 | 禁止事项 | 评价 |
|---|---|---|---|
| Coordinator | DAG、预算、指派、检查点 | 亲自伪装完成所有任务 | 完成率、预算、证据覆盖 |
| Research Tutor | 提问、解释、学习反馈 | 直接替学生跳过推理 | 学习增益、错误诊断 |
| Literature Agent | 文献集合、证据表 | 虚构论文或只读摘要下结论 | recall、precision、citation integrity |
| Idea Agent | gap、假设、风险 | 把“不同”直接称为创新 | novelty challenge 通过率 |
| Coding Agent | Patch、测试、实现说明 | 未审查写入主分支 | tests、diff 质量 |
| Experiment Planner | DAG、baseline、ablation | 假设资源或数据可用 | 覆盖率、成本估计 |
| Experiment Runner | Run、日志、artifact | 修改结论或隐藏失败 | 可复现率、遥测完整度 |
| Analyst | 统计、图表、误差分析 | 挑选有利结果 | 统计正确性、结论校准 |
| Writer | Claim-based manuscript | 生成无来源引用和数字 | citation/claim coverage |
| Figure Agent | 图表与 visual contract | 用视觉效果掩盖不利结果 | 可读性、数据一致性 |
| Reviewer | 模拟评审与修改清单 | 冒充真实 Reviewer | 缺陷召回、可操作性 |
| Release Agent | 网站、README、Poster | 发布未审批内容 | 一致性、可访问性 |

## 4. Skill 应该怎么写

Skill 不是一个长 Prompt。一个可维护的科研 Skill 至少包含：

```text
skill-name/
├── SKILL.md
├── schemas/
│   ├── input.schema.json
│   └── output.schema.json
├── prompts/
│   ├── system.md
│   └── repair.md
├── references/
│   └── rubric.md
├── evals/
│   ├── cases.jsonl
│   └── expected.json
└── scripts/
    └── validate.py
```

`SKILL.md` 必须回答：

- 何时触发和何时不触发；
- 输入 Artifact 类型和最低证据要求；
- 可以使用哪些工具；
- 输出 Artifact 的 owner 和 schema；
- 必须暂停的人工闸门；
- 失败、重试、预算和 early stop；
- 不允许虚构的内容；
- 如何验证完成，而不是让 Agent 自称完成；
- Skill、Prompt 和 rubric 的版本。

### Skill 优先清单

- `research-scoping`
- `literature-evidence-table`
- `paper-innovation-extractor`
- `novelty-challenger`
- `baseline-reproduction`
- `ablation-planner`
- `experiment-telemetry-audit`
- `result-statistics-check`
- `claim-evidence-audit`
- `venue-format-check`
- `simulated-reviewer`
- `rebuttal-matrix`
- `research-story-pack`
- `project-page-builder`
- `poster-builder`

## 5. Prompt 应该怎么写

Prompt 分为稳定层和动态层。

### 稳定层

- 角色职责；
- 科研诚信；
- 输出 schema；
- 工具政策；
- 失败和停止条件；
- 评价 rubric。

稳定层必须版本化，并放在 prompt cache 前缀。

### 动态层

- 当前任务；
- 检索得到的文献/记忆；
- Artifact 片段；
- 当前 Git/Run 状态；
- 用户补充约束。

动态内容必须放在后面，带 source 和截断信息。

### 推荐 Prompt 合同

```yaml
prompt_id: experiment-planner
version: 0.1.0
role: experiment_planner
inputs:
  - hypothesis
  - evidence_table
  - repository_manifest
  - compute_budget
required_outputs:
  - immutable_dag
  - success_metrics
  - resource_estimate
  - stop_conditions
forbidden:
  - fabricated_results
  - assumed_dataset_access
human_gate: scope
eval:
  - baseline_coverage
  - ablation_coverage
  - budget_feasibility
```

### Prompt 迭代流程

1. 从真实失败案例中建立 eval set。
2. 固定模型、工具和 Context Manifest。
3. 修改一个 Prompt 变量。
4. 跑离线评测。
5. 比较正确性、成本和稳定性。
6. 人工抽检高风险输出。
7. 记录版本、变化和回滚点。

禁止只凭“这段 Prompt 看起来更专业”升级生产版本。

## 6. 科研教育模式

每个生产 Agent 可以有一个 Tutor 模式：

```text
Do mode:     Agent 直接形成可审查 Artifact。
Teach mode:  Agent 先提问、让学生选择并解释反馈。
Assess mode: 隐藏答案，对学生方案按 rubric 评分。
Reflect mode:回顾决策、失败与下一步学习目标。
```

教育模式需要记录：

- 学生初始答案；
- Agent 提示层级；
- 学生修改；
- 最终答案；
- rubric 分数；
- 哪些误解重复出现；
- 哪些内容已经掌握，不应反复提示。

这类 learner memory 必须和科学事实记忆隔离，不能让“学生曾经误解某概念”污染论文
证据库。

## 7. 框架分层

```text
Interface
  CLI / Web / IDE / API / future chat channels

Application
  Mission / Session / Approval / Notification / Release

Harness Core
  Agent loop / Context builder / Tool broker / Memory / Budget / Eval

Scientific Domains
  Literature / Idea / Code / Experiment / Paper / Review / Education

Execution
  Local sandbox / Container / SSH / Slurm / LaTeX / Browser

Data
  PostgreSQL / pgvector / Object storage / Git / Event log
```

Harness Core 不应 import Web UI；科学领域不应直接执行 shell；执行器不应决定论文
结论；记忆层不应把所有文本都当成 verified fact。

## 8. 具体建设顺序（按依赖而非阶段）

### Durable Mission

- 新增 `missions`、`mission_nodes`、`mission_edges`、`checkpoints`、`leases`。
- 所有状态迁移使用 compare-and-swap。
- 节点重复投递必须幂等。
- Coordinator 只能 dispatch/monitor/evaluate/merge。

### Provenance Graph

- 建立 `claims`、`evidence_links`、`artifact_versions`。
- 将论文 Result Anchor、实验 Run、Commit 和 Figure 连接。
- 所有公开数字必须通过 evidence gate。

### Context Service

- Context Manifest、token budget、retrieval rationale。
- pgvector 只负责候选召回，最终排序加入 scope/status/time/provenance。
- 对 Policy、Learner、Scientific、Session memory 使用不同索引和 ACL。

### Tool Runtime

- Tool schema registry、权限、审批、审计。
- Local/Container/SSH/Slurm adapter。
- MCP 是连接协议之一，不是权限系统本身。

### Skill/Prompt Registry

- 版本、owner、输入输出 schema、eval、兼容矩阵。
- 不恢复公开 Skill 市场；先做审核过的内部 registry。
- 第三方 Skill 默认无网络、无秘密、无写权限。

### Evaluation

- Agent 单元测试：固定输入输出和 schema。
- Workflow 测试：DAG、恢复、幂等、失败补偿。
- Scientific eval：引用正确性、实验覆盖、统计错误、过度主张。
- Education eval：学习增益、提示依赖、错误迁移。

## 9. 尚未完成且必须进入 TODO

- 真正的数据库 Mission/DAG 调度器；
- Agent outbox/dispatch reconciler，避免 broker 故障制造重复任务；
- 自动 context compaction 与 retrieval evaluation；
- learner memory 与 scientific memory ACL；
- Prompt/Role/Skill Registry；
- Claude/Codex App Server adapter；
- OpenClaw/nanobot gateway bridge；
- MCP server 和 ResearchOS Tool SDK；
- Container/SSH/Slurm execution；
- PDF/figure/table/equation multimodal ingestion；
- 完整 provenance graph；
- 教学 rubric、课程模板和学习效果评测；
- CLI 二进制打包、自动更新和 shell completion；
- GitHub Release 签名、SBOM 和 provenance attestation。

## 10. 判断工程是否真的成功

不能只看 Agent 能否输出一篇“看起来像论文”的文本。成功标准是：

- 换一个模型仍能完成同一工作流；
- 中断后可以从 durable state 恢复；
- 任何结论都能找到证据和版本；
- 失败任务不会无限重试；
- 不同成员的数据和私有记忆不会串线；
- 学生能解释为何做这个实验，而不只是复制 Agent 输出；
- 同一结果在论文、README、网站和 Poster 中保持一致；
- 真实 Reviewer 提出问题时，可以快速定位相关 Claim、实验和代码。

这就是 ResearchOS 从“AI 科研界面”变成“科研与科研教育基础设施”的分界线。
