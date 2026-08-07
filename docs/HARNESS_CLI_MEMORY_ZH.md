# ResearchOS Harness、CLI 与科研记忆设计

## 1. 产品定位

ResearchOS 的目标不是重新实现一个通用聊天机器人，而是形成科研垂直领域的
Agent Harness：

```text
LLM Provider
    ↓ reasoning / tool calls
ResearchOS Harness
    ├── Context Builder
    ├── Tool Broker + Permissions
    ├── Agent / Workflow Runtime
    ├── Memory + Provenance
    ├── Experiment / Code / Paper Artifacts
    ├── Human Approval Gates
    └── CLI / Web / IDE / API
```

模型可以替换，Harness 保存可重复使用的科研能力。真正的产品资产不是某段
system prompt，而是：

- 论文、Claim、Idea、实验、代码、图表和稿件之间的可追溯关系；
- 可验证、可暂停、可恢复的科研工作流；
- 按角色、项目和人员隔离的工具权限；
- 对失败假设、负面结果和人工决策的长期记忆；
- 对模型、Prompt、Skill、数据与运行环境的版本记录。

## 2. 参考项目中采用和不采用的部分

| 项目 | 借鉴 | 不直接迁移的原因 | ResearchOS 做法 |
|---|---|---|---|
| [Claude Code](https://code.claude.com/docs/en/how-claude-code-works) | gather → act → verify、项目规则文件、会话恢复、人工中断 | 产品源码不可作为本项目代码来源，且主要面向软件工程 | 保留外部 CLI adapter；科研规则进入 `RESEARCHOS.md` |
| [OpenAI Codex](https://github.com/openai/codex) | model/tool loop、AGENTS.md、context compaction、sandbox/approval | Rust 架构和应用范围较大，整库迁移会形成维护与许可证负担 | 通过外部 Codex CLI/App Server adapter；不复制内部实现 |
| [OpenClaw](https://github.com/openclaw/openclaw) | gateway、Agent/workspace binding、长期运行、doctor、安全默认值 | 通讯渠道和个人助理不是科研主链路；Host tool 风险较大 | 借鉴 gateway 生命周期；科研工具默认 fail-closed |
| [nanobot](https://github.com/HKUDS/nanobot) | 小型 Python agent loop、CLI one-shot、会话、记忆、自动化 | Personal agent 的长期记忆不能直接等同科学证据 | CLI 保持小内核；科学记忆采用 provenance-first |

任何不能可靠迁移或许可证尚未核实的能力，只保留链接和 adapter TODO，不把外部
项目代码复制进 ResearchOS。

## 3. CLI 已实现的粗版

安装开发版：

```bash
cd apps/api
uv pip install -e .

researchos --help
# 简写
ros --help
```

初始化与连接：

```bash
researchos init
researchos config --api-url http://localhost:8000
researchos register --email you@example.com --display-name "Your Name"
researchos login --email you@example.com
researchos projects
researchos projects create --name "My Research"
researchos use <project-id>
researchos doctor
```

自动化环境可临时设置 `RESEARCHOS_PASSWORD` 并使用 `--password-env`；交互环境优先
使用隐藏输入。不要把密码写进仓库、命令历史或项目配置。

Agent 使用：

```bash
researchos ask "分析当前论文的创新点和缺失消融"
researchos ask --agent coding "检查训练代码的数据泄漏风险"
researchos chat
researchos runs list
researchos runs status <run-id>
researchos runs cancel <run-id>
```

记忆与上下文：

```bash
researchos memory add decision \
  "主指标采用 macro-F1，不能只报告 accuracy" \
  --source "2026-07-29 group meeting" \
  --status verified --confidence 1

researchos memory list --status verified
researchos context --render
```

服务端持久化 Research Mission（与网页工作台共享同一份数据）：

```bash
researchos missions create "研究低资源多模态分类" \
  --objective "形成带引用的综述与可复现实验方案" \
  --scope-json '{"minimum_papers":8,"year_from":2021}'
researchos missions list --status active
researchos missions show <mission-id>

# 保存阶段产物；不写 --version 时，CLI 会先读取最新版本并使用乐观并发控制
researchos missions step-save <mission-id> literature \
  --summary "已纳入 8 篇核心论文，形成 3 个主题簇" \
  --status needs_review
researchos missions approve <mission-id> literature --note "纳入标准与聚类已复核"
researchos missions timeline <mission-id>

# 阅读卡 Agent：生成结果写入 ReadingCardVersion，并可等待 AgentRun 完成
researchos missions generate-card <mission-id> <paper-id> --regenerate
researchos missions card-versions <mission-id> <paper-id>

# 综述：聚类大纲、章节证据 Agent、人工编辑与不可变历史
researchos missions review-outline <mission-id>
researchos missions review-generate <mission-id> <section-id> --regenerate
researchos missions review-save <mission-id> <section-id> --body-file review-section.md
researchos missions review-versions <mission-id>

# 实验方案：由综述生成、JSON 往返编辑、门禁校验并发布到 Experiment
researchos missions plan-generate <mission-id>
researchos missions plan-show <mission-id>
researchos missions plan-save <mission-id> --file experiment-plan.json
researchos missions plan-publish <mission-id>
researchos missions plan-versions <mission-id>

# 只读 SQL：先注册 JSON 快照，再让 SQL Agent 生成并执行受限查询
researchos missions dataset-register <mission-id> --file dataset.json
researchos missions dataset-list <mission-id>
researchos missions sql-query <mission-id> <dataset-id> "比较各方法的 macro-F1 均值"
researchos missions sql-results <mission-id>

# 引用整理：审计缺失元数据和重复项，并输出持久化 BibTeX
researchos missions citation-audit <mission-id>
researchos missions citation-show <mission-id>
```

`missions`（复数）调用正式 REST API；创建、阶段保存、人工确认、解锁和审计事件都由后端事务处理。`--input-json`、`--output-json` 与 `--scope-json` 均支持内联 JSON 或 `@path/to/file.json`，适合从 Harness 脚本提交结构化产物。

旧版单协调器 Mission 骨架（兼容保留）：

```bash
researchos mission run "研究低资源多模态分类并形成可投稿论文"
researchos mission status <mission-id>
researchos mission approve <mission-id> scope --note "指标和预算已确认"
```

单数 `mission` 命令只创建本地协调器记录，并派发一个已有 Research Agent；它不等同于复数 `missions` 的数据库五阶段任务，也不会自动派生多个 Worker Agent。

外部 Harness 适配器：

```bash
researchos adapters list
researchos adapters doctor
```

这一命令只发现已安装的 Claude、Codex、OpenClaw、nanobot 并提供链接，不会偷偷
安装或执行第三方程序。

## 4. 为什么科研记忆不能只是聊天记录

普通 Agent 常把“用户偏好”“历史对话”“事实”“执行结果”全部放进一个向量库。
科研场景中这是危险的：

- 模型建议不是事实；
- 论文摘要不是完整证据；
- 一次失败运行不能覆盖已验证结果；
- 最新结果不一定是最好结果；
- 导师的口头建议可能尚未确认；
- 相互冲突的实验必须同时保留，而不是被摘要抹平；
- 被否定的假设仍然有价值，可以避免重复浪费算力。

因此 ResearchOS 将记忆分为五层。

### 4.1 Policy Memory

来源：`RESEARCHOS.md`、`AGENTS.md`、项目安全规则。

内容：长期不变的工程约束、科研诚信规则、人工闸门和项目目标。

特点：每次会话加载，优先级最高，体积严格受限。

### 4.2 Semantic / Provenance Memory

来源：`.researchos/memory.jsonl`，未来迁移到数据库和 provenance graph。

记录类型：

- `decision`：为何选择某个方法、指标或数据集；
- `claim`：论文主张以及支持或反对证据；
- `experiment`：实验结论、run、commit、环境和 artifact；
- `preference`：用户或实验室约定；
- `failure`：失败假设、负面结果和根因；
- `handoff`：人员或 Agent 之间的交接。

每条记录包含：

```json
{
  "id": "uuid",
  "kind": "claim",
  "content": "Method A improves macro-F1 on dataset D",
  "source": "run:... / paper:...",
  "status": "candidate | verified | rejected | superseded",
  "confidence": 0.9,
  "scope": "project",
  "tags": ["dataset-d", "main-result"],
  "supersedes": null,
  "created_at": "ISO-8601"
}
```

### 4.3 Episodic Memory

来源：`.researchos/sessions/*.jsonl` 与未来的数据库事件流。

内容：用户消息、Agent 回复、工具调用、审批、暂停、失败和恢复。

特点：append-only，可回放；默认不提交 Git，避免泄漏临时讨论和敏感信息。

### 4.4 Artifact Memory

来源：代码、论文、实验 artifact、图表、数据版本和 Git commit。

这些内容不应完整复制到 LLM 记忆中。长期记忆只保存引用、摘要、hash 和 provenance
边，需要时再按需读取原始 Artifact。

### 4.5 Working Context

当前 turn 真正送给模型的有限上下文。它是动态构建结果，不是永久记忆。

当前优先级：

```text
RESEARCHOS.md
  > AGENTS.md
  > verified/candidate scientific memory
  > Git workspace state
  > recent session
  > current user task
```

静态规则放在前面、动态内容放在后面，便于模型提供商进行 prompt prefix cache。

## 5. Context Builder 约束

Context Builder 必须输出 Context Manifest：

- 使用了哪些来源；
- 每个来源占用多少字符/token；
- 哪些内容被截断；
- 每条事实的状态与 source；
- 使用的 Prompt、Skill、Role、Tool schema 版本；
- Artifact 的 commit/hash/version；
- 当前可用工具与审批模式。

不能依靠“把整个项目塞进上下文”。正确策略是：

1. 先放不可违反的 Policy。
2. 按任务检索 Claim、Decision、Failure 和 Experiment。
3. 只加载所需 Artifact 片段。
4. 日志和 PDF 原文保留外部引用。
5. Context 达到阈值时先删除可重取的工具输出。
6. 再生成结构化 compaction，并保留 source id。
7. 连续 compaction 后仍超限时停止，要求用户缩小范围。

## 6. 后续协议

计划增加：

- `researchos.context/v2`：token 预算和 retrieval rationale；
- `researchos.memory/v2`：数据库事件、ACL、supersedes 图；
- `researchos.mission/v1`：持久化 DAG、lease、heartbeat、budget；
- `researchos.tool/v1`：参数 schema、权限、sandbox、审计和结果摘要；
- `researchos.checkpoint/v1`：scope/evidence/release 人工审批；
- `researchos.adapter/v1`：Claude/Codex/OpenClaw/nanobot 外部执行适配。

在协议冻结前，CLI 只使用稳定现有 REST API，并将 Mission 功能标为 scaffold。
