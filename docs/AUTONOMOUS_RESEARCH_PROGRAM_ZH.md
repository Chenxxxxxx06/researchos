# ResearchOS 长程多 Agent 科研闭环

状态：Implemented bounded vertical slice  
适用版本：数据库迁移 `0027`、`0028` 之后

## 1. 设计结论

ResearchOS 使用一个持久化 Coordinator，而不是让 Agent 自由互聊。Agent 之间只交换带哈希、版本、来源和验收条件的 Artifact/Handoff；Coordinator 负责 DAG、重试、预算、权限、停止条件和人工门禁。

当前标准科研图包含 26 个有效节点：

```text
scope
→ discover
→ read
→ synthesize
→ idea_rank + benchmark
→ critic
→ direction
→ repository
→ baseline + coding
→ code_check
→ pilot
→ pilot_review
→ leader
→ experiment_plan
→ experiment_run
→ progress
→ reproduce
→ analyze
→ writer_outline → writer_results
→ drawer + citation
→ review
→ release
```

`writer_outline` 在选定方向后即可并行启动，因此论文框架可以边研究边写；结果段、表格、图和最终引用仍必须等待实验 Artifact。

## 2. Agent 掌控范围

`GET /projects/{project_id}/agents/capabilities` 返回运行时能力账本。它区分静态能力与 operational readiness：没有启用模型时显示 `needs_model`，不能把“类已注册”冒充“当前可运行”。

| Agent | 唯一主责 | 自动权限 | 硬边界 |
|---|---|---|---|
| Research | 检索、导入、跨论文综合 | 只读检索；provider 验证后导入 | 不得编造论文 |
| Paper Reader | 摘要、实验结果、代码、Idea、Benchmark、消融、多元组 | 写版本化 ReadingCard | 逐字 quote 校验 |
| Idea Explorer | 证据排序 Top 10 | 创建 draft Idea | 仅允许 Mission 论文 ID |
| Benchmark | Benchmark、baseline、seed、pilot/full matrix | 写计划 Artifact | 不得生成结果 |
| Critic | 新颖性、缺 baseline、风险 | 写 Critique | 不批准自己 |
| Leader | 一次选择一个方向、决定 revise/pilot/scale/stop | 重排有界任务 | API、仓库、全量算力受 Gate 约束 |
| Coding | 读代码、生成 Patch、测试修改 | 默认只 Patch；受信任项目工作区可自动 apply | read-before-write、Git commit 必须存在 |
| Viewer | code/pilot/final review | 只写 verdict | 不能修改被审对象 |
| Experiment Planner | 完整实验与消融 DAG | 写版本化 ExperimentPlan | 不启动付费计算 |
| Experiment | 从真实 metric 计算结果 | 只读 Run/Metric | 不编辑数字 |
| Progress | Agent、Task、Run、阻塞与 ETA 基础 | 监控 | 不批准任务，不虚构 ETA |
| Writer | venue-aware LaTeX section | 写独立版本化 section 文件 | 解析并阻止未知 cite key/数字 |
| Drawer | Mermaid、FigureSpec、LaTeX 表格、caption | 生成并渲染有来源图 | 禁止 inline 虚构序列 |
| Citation | BibTeX、重复和缺失项 | 写审计 Artifact | 缺失字段不猜测 |
| LaTeX | 局部 tracked suggestion | 建议 | CAS + 人工接受 |

## 3. 单论文提取与多元组 RAG

Paper Reader 从用户允许的章节提取：

- 核心摘要与研究问题；
- 方法流程；
- 实验设置与关键结果；
- 作者结论、优势、限制与复现要求；
- GitHub/代码仓库 URL；
- 可复用研究 Idea；
- Benchmark、数据切分、指标和协议；
- 消融组件、对照、效果与指标；
- `summary/result/code/idea/benchmark/ablation/limitation` 多元组。

每个结构项保留 `section_id`、逐字 `quote`、`inference` 与 `evidence_status`：

```text
reported           论文原文直接报告，且 ReadingCard 已复核后才计入可信排序
context_grounded   Idea 是推断，但动机 quote 可定位
needs_evidence     没有可验证原文
```

`paper_knowledge_tuples` 使用 pgvector + PostgreSQL FTS。检索模式为：

```text
hybrid-vector-keyword-tuples-v3
```

Paper chunk 与 tuple 分别做 vector/keyword recall，再统一 RRF；每篇论文默认最多 3 个优先结果。Embedding profile 变化时，chunk 和 tuple 都会自动重建。

## 4. Top 10 方向和 Benchmark 排序

`GET /missions/{mission_id}/research-synthesis` 返回：

- Top 10 directions；
- benchmark shortlist；
- paper/card/tuple coverage。

方向分数版本 `paper-insight-ranking-v1`：

```text
0.30 × reviewed reported evidence
+ 0.20 × cross-paper support
+ 0.20 × benchmark coverage
+ 0.15 × ablation support
+ 0.10 × code availability
+ 0.05 × human review coverage
```

Benchmark 可信度优先考虑：多篇论文出现、原文证据已复核、明确 metric、明确 split/protocol、代码可用、可用于消融。该分数是检索/实验设计优先级，不是科学结论或录用概率。

`POST /research-synthesis/materialize` 将 Top 10 固化为 draft Idea；Idea Explorer 可以用模型进一步重排，但只能使用 allowlisted paper IDs。

## 5. Pilot-first 自动循环

启动入口：

```http
POST /projects/{project_id}/orchestration/missions/{mission_id}/autopilot
```

关键策略：

- `max_directions <= 10`；
- `pilot_first=true`；
- 一个方向一次只改一个有界实现；
- Code Viewer 未通过不能进入 pilot；
- Pilot Viewer 报告交给 Leader；
- Leader 可选择 `revise_code`、`continue_pilot`、`try_direction`、`scale_experiments`、`write`、`stop`；
- revision 会重置明确的一段任务，而不是重跑整个 Mission；
- next direction 会归档当前方向，重新执行 Critic、Direction 和 Repository Gate；
- 达到方向预算后确定性 stop。

AgentRun 完成后发送 `orchestration.advance`，下一节点由 Worker 继续。Broker 失败时任务和 Handoff 仍留在数据库，可通过 `Start / continue autopilot` 或 Coordinator tick 恢复。

## 6. Coding 与执行安全

自动 apply 不是默认的共享仓库写入权限。它必须同时满足：

1. 使用 ResearchOS 默认项目工作区；
2. 用户勾选 trusted auto-code + pilot；
3. Patch 通过 read-before-write 和原子文件应用；
4. Git workspace 初始化成功；
5. 必须生成非空 commit SHA；
6. Git commit 失败时文件回滚，Patch Gate 不自动批准。

本机 Runner 只接受：

```text
pytest ...
python -m pytest ...
python -m compileall ...
```

任意训练脚本、包管理器、外部 API、网络访问或大规模 GPU 应使用受控 SSH/container Runner。当前 trusted local 模式不是微虚拟机，UI 明确要求用户确认，不能描述为强隔离。

Runner 记录：argv、cwd、exit code、duration、timeout、stdout/stderr SHA-256、Git commit、日志、指标和 execution receipt。科学脚本可输出：

```text
RESEARCHOS_METRIC {"name":"accuracy","step":1,"value":0.91}
```

未记录科学主指标时，Viewer 会强制 `revise`，不能仅凭 `command_success=1` 放大为实验收益。

## 7. Handoff 与跨 Mission 隔离

每个成功任务写两个 Artifact：

1. canonical `agent-run/<type>` Artifact；
2. `researchos.handoff/v1` Artifact。

Handoff 的 `output.artifact_id/sha256/version` 必须与 canonical Artifact 完全一致。Dispatch 时 Coordinator 解析直接依赖 Artifact，并把精确版本写入 `input_artifacts`；接收方不能只靠聊天历史猜上游状态。

Idea、Run、Viewer、Writer、Drawer snapshot 全部按 `mission_id` 过滤。Pilot/full Run 还绑定 `mission_task_id` 和 `scale`，不能用另一个 Mission 的“最新 Run”解锁当前节点。

## 8. Writer、Drawer 与论文模板

Writer 会：

- 读取 Mission 论文、任务 Artifact 和 ExperimentRun；
- 验证 LaTeX 内的每个 `\cite{}`；
- 验证数字是否来自记录的 metric；
- 将章节写到 `sections/autopilot-<section>.tex`，不静默覆盖 `main.tex`；
- 保留版本历史。

Drawer 会：

- 生成 LR Mermaid method flow；
- 做危险指令和括号结构 preflight；
- 只接受 `run_metric` FigureSpec，禁止 autonomous inline values；
- 服务器重新计算图表来源 Run；
- 校验表格数字；
- 写入 `.mmd`、Markdown preview 和 LaTeX table 文件。

本地 venue starters：NeurIPS、ICML、ICLR、CVPR、ACL、AAAI，加上 Article、IEEE、ACM、Elsevier。Starter 仅使用本地 TeX Live/MiKTeX 核心包以便离线编译；正式投稿前必须按记录的 official URL 同步当年官方 class/style。

## 9. 每日论文推荐

Research Feed 独立实现了 Zotero library recency-weighted similarity 思想：候选论文与整个项目库比较，最近加入的研究兴趣权重更高，再与 provider RRF 和论文新鲜度融合。

算法标签：

```text
zotero-library-recency-weighted-rrf-v2
```

参考项目 `TideDra/zotero-arxiv-daily` 使用 AGPL-3.0。本仓库没有复制其源码；只依据公开 README 描述独立实现算法，以避免把 AGPL 网络分发义务混入当前专有代码。当前 Feed 是拉取式报告，不包含 SMTP 推送守护进程；邮件/系统通知仍需单独的 Secret Store 与 Scheduler。

## 10. 诚实运行边界

无模型凭证时：Capability Ledger 显示 `needs_model`，Autopilot 返回 `model_config_required`。  
无论文时：自动阅读停止并要求导入论文。  
无仓库批准时：Repository Gate 停止。  
无安全 pilot command/执行确认时：Pilot 停止。  
无科学主指标时：Viewer 阻止 scale。  
无 full compute 批准时：完整实验停止。  
无引用或数字证据时：Writer/Drawer 失败，不输出伪造稿件。

因此可以诚实称为“可恢复、Pilot-first、证据约束的长程科研闭环骨架和本地有界执行纵切”，不能称为“无需凭证、数据、仓库和算力即可完成真实论文”的系统。
