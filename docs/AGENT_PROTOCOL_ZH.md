# ResearchOS 多人协作树与 Agent 协议

## 两种结构必须分开

ResearchOS 同时使用“归属树”和“任务 DAG”：

```text
Organization
└── Project
    ├── Member A
    │   ├── private worktree
    │   ├── missions
    │   └── agent runs / drafts / notes
    ├── Member B
    │   └── ...
    └── Shared
        ├── evidence
        ├── approved code commits
        ├── experiment results
        └── manuscript
```

归属树回答“内容是谁的、谁能看、从哪里产生”。任务 DAG 回答“谁依赖谁、哪些能并行、
失败后重跑什么”。不能用目录树表达实验依赖，也不能用 DAG 代替权限边界。

建议的可见性：

- `private`：创建者和项目管理员；
- `team`：项目成员；
- `published`：被明确批准进入共享证据、主分支或论文；
- 所有实体保留 `created_by`、`owner_user_id`、`worktree_id`、`mission_id` 和版本哈希。

## 一个 Coordinator，多个执行角色

Coordinator 只做以下工作：

1. 把目标拆成有验收条件的任务；
2. 检查依赖、权限、预算和风险；
3. 分配给一个明确的 artifact owner；
4. 监听事件、续租、重试或暂停；
5. 验证 handoff；
6. 请求人工批准；
7. 不亲自写论文、不跑实验、不伪造审稿意见。

子 Agent 不直接创建另一个子 Agent，也不通过自然语言私聊改变任务。它们只能向
Coordinator 发送协议消息，由 Coordinator 修改 DAG。这避免递归失控、权限扩张和责任不清。

建议角色：

| Agent | 唯一主责产物 | 不能做的事 |
|---|---|---|
| Evidence | 文献记录、证据锚点、引用图谱 | 编造引用、替实验下结论 |
| Idea | 可证伪假设、idea brief | 把猜测写成已验证创新 |
| Coding | 补丁、测试、commit 候选 | 自行合并主分支 |
| Experiment Planner | baseline/benchmark/ablation DAG | 生成虚构结果 |
| Experiment Runner | run、日志、指标、artifact | 改论文结论 |
| Reproducibility | 环境锁、重跑、结果 diff | 隐藏负结果 |
| Writer | manuscript 与引用/结果锚点 | 引用无来源数字 |
| Figure | 图、表、公式、poster、项目页面 | 手工篡改实验数值 |
| Reviewer | venue rubric review、score、修改清单 | 直接覆盖稿件 |
| Release | README、project page、投稿包 | 未经确认公开或投稿 |

## Handoff Envelope v1

Agent 之间不传“你看着办”，而传机器可校验的 envelope：

```json
{
  "protocol": "researchos.handoff/v1",
  "message_id": "uuid",
  "mission_id": "uuid",
  "task_id": "uuid",
  "parent_task_id": "uuid-or-null",
  "sender": {"kind": "agent", "role": "experiment-runner", "run_id": "uuid"},
  "recipient": {"kind": "agent", "role": "reproducibility"},
  "type": "artifact_ready",
  "idempotency_key": "mission/task/attempt/output",
  "inputs": [{"artifact_id": "uuid", "sha256": "...", "version": 3}],
  "outputs": [{"artifact_id": "uuid", "sha256": "...", "schema": "experiment-result/v1"}],
  "claims": [{"claim_id": "uuid", "support": ["artifact:uuid"]}],
  "preconditions": ["code_commit_locked", "dataset_version_locked"],
  "acceptance": ["all_seeds_finished", "primary_metric_present"],
  "permissions": ["workspace:read", "experiment:write"],
  "budget": {"tokens": 20000, "gpu_minutes": 120, "wall_seconds": 10800},
  "status": "ready_for_review",
  "error": null,
  "created_at": "ISO-8601"
}
```

接收方必须校验：

- schema/version 支持；
- input artifact 哈希没有变化；
- sender 是否拥有声明权限；
- acceptance 是否满足；
- idempotency key 是否已经处理；
- 未通过则返回结构化 `rejected`，不能默默修正上游产物。

## 任务状态机

```text
draft
  → ready
  → leased
  → running
  → artifact_ready
  → verifying
  → completed

running → waiting_approval
running → retryable_failed → ready
running → terminal_failed
any non-terminal → cancelled
```

每个运行任务必须有 `lease_owner`、`lease_expires_at`、`heartbeat_at`。Worker 崩溃后，
租约过期才能由新 Worker 接管；所有副作用依赖 idempotency key。

## “不停轴”不是无限循环

连续运行由 Scheduler 事件循环完成，而不是一个永不退出的大 Prompt：

```text
load mission state
→ find ready DAG nodes
→ check permissions/budget/gates
→ lease runnable nodes
→ dispatch workers
→ consume progress/artifact/error events
→ verify outputs
→ unlock downstream nodes
→ stop when completed, paused, blocked, over-budget or no progress
```

推荐停止条件：

- DAG 全部完成；
- 同一错误重试达到上限；
- 连续两轮没有新增 artifact 或指标改善；
- token/GPU/时间预算达到 90% 时暂停；
- 证据、完整性或复现 gate 失败；
- 用户取消或项目被归档。

必须人工确认：

- 首次连接 SSH 主机和 host key；
- 付费 API、大规模 GPU 和外部数据上传；
- 合并主分支、删除/覆盖文件；
- 主指标和最优方案选择；
- integrity gate override；
- 作者、投稿会议和最终提交；
- 发布 GitHub Pages、poster 或公开仓库。

## Prompt 与角色版本

Prompt 不应硬编码在 Worker 代码中。使用版本化注册表：

```text
role_id
prompt_version
skill_refs[]
input_schema
output_schema
allowed_tools[]
forbidden_actions[]
quality_gates[]
model_policy
checksum
status: draft | canary | active | retired
```

每次 Agent run 固定记录 `role_id + prompt_version + model + tool versions`。更新提示词先跑
golden cases / regression eval，再从 canary 切到 active；旧任务继续使用原版本，保证可复盘。

## 多人冲突

- 文献笔记、Idea、Inbox 默认有明确 owner；
- 代码编辑在成员 worktree/branch 中进行，通过 patch review 合入共享主线；
- 论文使用 suggestion/revision，而不是最后写入者覆盖前人；
- 实验 run 绑定 code commit、数据版本和发起人；
- 冲突记录追加写入，不删除历史；
- Research Lead 决定范围，Methods Owner 决定方法，Lead Author 决定表达，Integrity gate
  不能被普通角色绕过。

## CLI 封装方向

未来可暴露统一命令：

```text
researchos mission start "一句话目标"
researchos mission status <id>
researchos mission approve <gate>
researchos agent list
researchos run local -- <argv...>
researchos run ssh --profile gpu-a -- <argv...>
researchos paper review --venue neurips
researchos reproduce <run-id>
researchos package submission
```

CLI 与网页必须调用同一套 API、权限、状态机和审计日志，不能另写一套不可追踪的执行逻辑。
