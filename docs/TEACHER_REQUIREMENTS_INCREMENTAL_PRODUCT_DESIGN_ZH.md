# 科学文献研究智能体：老师要求对齐与增量产品设计

> 设计对象：ResearchOS（当前仓库）
> 需求来源：《科学文献研究智能体：从综述到实验设计》
> 设计目标：不推翻现有 ResearchOS，以“科研任务 Mission”为主线，把已经分散的文献、Agent、实验、写作和团队能力组织成可操作、可追溯、可演示的完整闭环。
> 状态口径：本文中的“已有”必须能在当前代码中找到真实页面、API 或持久化对象；“设计新增”不等于已经实现。

最终逐项交付状态、8 分钟演示顺序和可复跑命令见 [老师要求逐项验收矩阵](TEACHER_REQUIREMENTS_ACCEPTANCE_MATRIX_ZH.md)。

## 0. 产品结论

当前项目不是从零开始。论文检索与导入、论文分节阅读、Research Agent、Idea/Critic、实验运行与指标、LaTeX 写作、Zotero、团队成员和 Agent Run 都已有真实骨架。

真正的问题是：

1. 老师要求的是“从主题到综述、再到实验方案”的一条工作流，现有能力却分散在 12 个侧边栏入口中。
2. 阅读卡、页内笔记和引文定位已经形成可管理初版，后续重点是批量复核与上游变化后的 stale 提醒。
3. Mission 已接入向量 + 关键词 + 引用片段的混合 RAG；外部语义 embedding provider 仍是可替换增量。
4. Experiment/Run 之外已增加 Mission 级 ExperimentPlan；下一步是把发布后的矩阵进一步转换为批量 Run。
5. 主题聚类、综述章节、实验规划、只读 SQL 和引用整理专项 Agent 已落地；浏览器流式语音转写与统一管理中心也已接入现有工作区。
6. Teacher Demo 已扩展为 8 篇明确标注为虚构演示材料的论文、3 个主题簇、8 张阅读卡、3 条笔记、结构化综述、实验方案和数据快照，可稳定展示完整链路且不会把演示材料冒充真实出版物。

因此，本次设计采用一个明确的增量策略：新增“科研任务 Mission”作为主入口；已有页面继续作为专业工具页，通过 Mission 的步骤和产物链接被串起来。

### 0.1 当前实施进度（2026-08-06）

| 增量 | 已落地的真实位置 | 当前边界 |
|---|---|---|
| Mission 主线 | `/missions` 列表、`/missions/[missionId]` 五阶段工作台；`ResearchMission`、`MissionStep`、`MissionEvent`；迁移 `0010` | 五阶段均有持久化产物；统一完成度门禁仍需与各专用编辑器指标联动 |
| CLI / Harness | `missions` 下的任务、阅读卡、综述与实验方案命令 | 与网页共用 API、权限、AgentRun、乐观版本与不可变版本；旧单数 `mission` 仅为兼容脚手架 |
| 任务论文集 | Mission“文献与聚类”阶段；`MissionPaper`；`/missions/{id}/papers` | 当前从已导入项目论文库纳入；外部联邦检索仍在 Research 页面 |
| 证据检索 | Mission 文献阶段的跨论文“论文—章节—片段”结果；`PaperChunk`；PostgreSQL GIN + pgvector HNSW；`POST /rag/search` | 已实现 `hybrid-vector-keyword-v1`；默认 `hashing-384-v1` 可离线复现，后续可替换为外部语义 embedding provider |
| 主题聚类 | Mission 文献阶段“生成/重建”；`MissionTopicCluster`；迁移 `0011/0012` | 已使用 384 维论文向量与 average-linkage 层次聚类形成可重复初始簇；合并/拆分/拖动仍待增强 |
| 结构化阅读卡 | Mission“阅读卡”阶段；`ReadingCard/ReadingCardVersion`；专用 `reading_card` Agent | Agent 只接收已解析章节，claim 必须通过 section UUID + 原文引句校验；生成版进入 `needs_review`，人工编辑和每次生成均保存不可变版本 |
| 页内阅读笔记 | `/research/read/[paperId]?mission=...` 章节标题“笔记”与右侧笔记栏；`ReadingNote` | 支持章节、引句、标签和任务过滤；移动端笔记抽屉待补 |
| 结构化综述 | `/missions/[missionId]/review`；`ReviewDocument/ReviewSection/ReviewVersion`；`review_section` Agent；迁移 `0014/0015` | 聚类生成章节；章节按选定论文读取原文、逐条校验 claim 引句并进入人工复核；当前版本历史为快照列表，差异视图待增强 |
| 结构化实验方案 | `/missions/[missionId]/experiment-plan`；`ExperimentPlan/ExperimentPlanVersion`；`experiment_planner` Agent；迁移 `0016` | 可编辑变量、基线、数据、指标、矩阵、规则、风险与复现清单；发布门禁通过后创建真实 `Experiment`；批量 Run 派生待增强 |
| 只读 SQL Data Lab | `/missions/[missionId]/data-query`；`DatasetSource/SqlQueryResult`；`sql_analyst` Agent；迁移 `0017` | 仅在已注册 JSON 数据的隔离内存 SQLite 快照中执行单条 `SELECT/WITH`；写操作、注释、多语句和 SQLite 系统表均拒绝 |
| 流式语音记录 | Research Inbox 的“流式语音记录”；浏览器 `SpeechRecognition` 连续模式 | Chrome/Edge 中显示临时与最终转写并写入现有 Inbox 文本；不保存原始音频，不支持时明确降级，不虚报成功 |
| 引用整理 | `/missions/[missionId]/citations`；`MissionCitationAudit`；`citation_organizer` Agent；迁移 `0018` | 审计缺失元数据、DOI/arXiv/标题重复项并导出 BibTeX；缺失字段只告警、不猜测 |
| 统一管理中心 | `/projects/[projectId]/manage`；`GET /manage/summary` | 从真实组织、项目、成员、论文、实验方案和阅读笔记聚合；编辑动作深链到原工作区并沿用同一权限模型 |
| Teacher Demo 与 E2E | `researchos.seed.demo`；`apps/web/e2e/mission-requirements.spec.ts` | E2E 固定检查 Mission、综述证据、实验门禁、SQL、引用、语音和管理入口；完整数据库联测需要本机 PostgreSQL 安装 pgvector |

以上条目均为当前代码中的真实页面、API 或数据库对象；未完成项继续沿用本文后续设计，不以占位 UI 冒充完成。

## 1. 当前能力审计

### 1.1 可直接复用

| 能力 | 当前真实载体 | 在新设计中的角色 |
|---|---|---|
| 组织、项目、成员与角色 | `organizations`、`projects`、成员 API | 课题组、科研项目、研究人员的权限基础 |
| 联邦论文检索与导入 | Research 右栏 Discover；`/papers/search`、`/papers/import` | Mission 的“检索与纳入”步骤 |
| 论文库 | Research 左栏 Paper Library | Mission 的证据集合和引用来源 |
| 论文分节解析 | `PaperSection`；Reading Room | 结构化阅读卡与 RAG 的原始语料 |
| Research Agent | `ResearchAgent`，支持 `paper.search`、`library.list`、`paper.sections` | 文献问答、证据解释和后续专项 Agent 的运行底座 |
| 缺口挖掘与 Idea | `gap_matrix.py`、Idea/Critic | 研究空白与研究问题候选 |
| 实验与运行 | Experiment、Run、Metric、Log、Artifact | ExperimentPlan 获批后的执行层 |
| 论文写作与引用 | Paper Workspace、Cite、Anchor、Figure | 综述草稿和实验结果进入论文的出口 |
| Zotero | References Workspace 与 Zotero API | 引用整理和外部文献同步 |
| Agent 运行记录 | AgentRun、ToolCall、Event | Mission 历史、证据链和可解释性 |
| Research Inbox | 消息、笔记、转写稿与分析 | 导师输入和语音转写稿进入 Mission 的入口 |

### 1.2 设计启动时的基线缺口（保留用于说明为何采用增量方案）

| 老师要求能力 | 当前情况 | 缺口判断 |
|---|---|---|
| 论文资料 RAG | 能读取论文分节并注入 Agent；没有 `paper_chunks`、embedding、pgvector 召回和全文关键词检索 | 部分可用 |
| 论文摘要 | Paper 有 `summary` 字段，Agent 可生成回答；没有结构化摘要生成、版本和审核状态 | 部分可用 |
| 方法/实验/结论检索 | PaperSection 已分类 method/experiments/results/conclusion；未提供跨论文混合检索页面 | 部分可用 |
| 阅读模块 | 可看分节全文、解释论文、提取创新点；没有研究问题、方法流程、优缺点、复现要点的固定阅读卡 | 部分可用 |
| 实验设计 Agent | 现有 Experiment Agent 只分析已有指标；实验页只有一段静态规划建议 | 部分可用 |
| 流式语音科研助手 | 可保存“录音转写稿”；音频只记录文件名，要求用户粘贴转写文本 | 部分可用，不得宣称 ASR 已完成 |
| 后台管理 | 组织/项目/成员有 API；文献/实验也有各自 API；没有统一管理中心 | 部分可用 |

### 1.3 设计启动时确定的增量范围

- ResearchMission 持久化主线和步骤状态。
- 主题聚类及人工调整。
- 结构化阅读卡、阅读笔记、引用锚点。
- 综述大纲和综述草稿版本。
- 结构化 ExperimentPlan、变量设计和从方案发布到 Experiment/Run。
- 只读、受限、可审计的科研数据 SQL Agent。
- 真正的流式音频转写适配器和带引用的语音问答。
- 课题组/项目/人员/文献/实验方案/笔记统一管理页。
- 可稳定复现老师验收流程的 Demo 数据与演示模式。

## 2. 信息架构

### 2.1 侧边栏调整

保留现有路由，不做框架迁移；把过长的平铺导航改为分组，并增加一个主入口。

```text
项目
├─ 概览
├─ 科研任务（新增，主入口）
│
├─ 调研
│  ├─ Research Copilot（原 Research）
│  ├─ 文献中心（原 References）
│  └─ 科研收件箱（原 Inbox）
│
├─ 实现与实验
│  ├─ AI IDE
│  └─ 实验运行（原 Experiments）
│
├─ 写作与交付
│  ├─ 论文工作台
│  ├─ 模拟审稿
│  └─ 成果发布
│
└─ 管理
   ├─ 课题组与 Agent（原 Orchestration，增量扩展）
   ├─ 截止日期
   └─ 设置
```

### 2.2 新增路由

| 路由 | 页面 | 作用 |
|---|---|---|
| `/projects/[projectId]/missions` | 科研任务列表 | 新建主题、查看进度、恢复历史任务 |
| `/projects/[projectId]/missions/[missionId]` | 科研任务工作台 | 从主题到综述和实验方案的唯一主线 |
| `/projects/[projectId]/missions/[missionId]/review` | 综述编辑器 | 大纲、段落、引用覆盖率与版本对比 |
| `/projects/[projectId]/missions/[missionId]/experiment-plan` | 实验方案编辑器 | 变量、对照、数据集、指标、预算和批准 |
| `/projects/[projectId]/missions/[missionId]/data-query` | 只读数据实验室 | 注册数据快照、自然语言转 SQL、结果与审计历史 |
| `/projects/[projectId]/missions/[missionId]/citations` | 引用整理器 | 元数据缺失、重复项与 BibTeX 导出 |
| `/projects/[projectId]/manage` | 管理中心 | 课题组、人员、项目、文献、方案和笔记管理 |

现有 `/research`、`/research/read/[paperId]`、`/experiments`、`/paper` 等路径保留；Mission 页面使用深链接打开它们，并携带 `missionId` 作为上下文。

## 3. 核心页面设计

### 3.1 科研任务列表

#### 展示位置

侧边栏“科研任务”进入；项目概览首屏增加“开始一次文献研究”主按钮。

#### 页面结构

- 顶部：主题输入框、研究领域、时间范围、目标（综述/选题/实验设计）。
- 中部：进行中任务，以当前步骤、论文数、未确认问题、更新时间显示。
- 下部：已完成与已归档任务，可进入历史版本。
- 首次空状态：给出一个真实示例主题，不生成假数据。

#### 实际操作

1. 用户输入研究主题。
2. 系统创建 Mission 草稿，只生成范围建议，不立即自动跑完。
3. 用户确认关键词、纳入/排除标准、时间范围和预期产物。
4. 确认后进入 Mission 工作台并启动文献检索。

### 3.2 科研任务工作台

#### 主视觉结构

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ 主题：弱监督医学图像分割中的不确定性建模       状态：正在阅读  证据覆盖 72% │
│ [1 范围]—[2 文献与聚类]—[3 阅读卡]—[4 综述]—[5 实验方案]                    │
├───────────────┬──────────────────────────────────────┬─────────────────────┤
│ 本步对象       │ 当前工作区                            │ 证据与运行轨迹       │
│               │                                      │                     │
│ 文献/聚类/     │ 根据步骤显示：                       │ 引用片段             │
│ 阅读卡/大纲/   │ - 文献矩阵                           │ Agent 工具调用        │
│ 变量与方案     │ - 阅读卡编辑                         │ 假设与待确认项        │
│               │ - 综述大纲与草稿                     │ 版本/历史             │
│               │ - 实验方案编辑器                     │                     │
├───────────────┴──────────────────────────────────────┴─────────────────────┤
│ 下一步建议：3 篇核心论文尚未生成阅读卡   [生成并审核] [查看缺口] [继续]      │
└────────────────────────────────────────────────────────────────────────────┘
```

#### 交互原则

- 不能“一键自动完成”后只给一段文本；每一步都有结构化产物和人工确认。
- 每个生成按钮显示输入来源、使用的 Agent、模型、工具和产物版本。
- 没有来源支持的内容显示“待证据”，不能混入正式综述。
- 所有步骤可回退；回退后下游产物标记为“可能过期”，不静默覆盖。
- 右栏始终展示证据和运行轨迹，使老师能看到 Agent 具体做了什么。

### 3.3 文献与主题聚类

#### 展示位置

Mission 第 2 步；同时复用 Research Copilot 的外部检索和导入能力。

#### 页面组件

1. 检索策略条：关键词、同义词、时间、来源、纳入/排除标准。
2. 文献表：标题、年份、来源、摘要、相关度、纳入状态、解析状态、引用数。
3. 聚类画布：按主题分组显示论文；支持“重命名、合并、拆分、拖动论文”。
4. 对比矩阵：论文 × 方法/数据集/任务/指标/结论/局限。
5. 证据抽屉：点击任一结论，显示原文片段、章节和来源。

#### 聚类实现

- 第一阶段使用 embedding 相似度 + 层次聚类，确保结果可重复。
- LLM 只负责给聚类命名和解释，不决定论文归属。
- 用户人工调整后保存为新的 cluster version。
- 聚类结果作为综述大纲的一级主题候选。

### 3.4 论文详情、结构化阅读卡和笔记

#### 展示位置

保留现有 `/research/read/[paperId]`，在正文上方增加“阅读卡”页签，右侧增加“笔记/引用”栏。

#### 阅读卡固定字段

| 字段 | 生成来源 | 用户动作 |
|---|---|---|
| 一句话摘要 | abstract + conclusion | 编辑、确认 |
| 研究问题 | introduction + abstract | 确认或改写 |
| 方法流程 | method sections | 查看步骤图、编辑步骤 |
| 数据与实验 | experiments/results | 补充数据集、基线、指标 |
| 主要结论 | results + conclusion | 每条结论必须绑定引用片段 |
| 优点 | 全文证据 | 接受/驳回 |
| 缺点与局限 | limitation/conclusion/critic | 标记显式局限或推断局限 |
| 可复现要点 | method/implementation/appendix | 形成 checklist |
| 对当前主题的价值 | Mission scope + paper | 纳入综述、仅作背景、排除 |

#### 阅读笔记

- 笔记不是一个自由文本大框，而是支持普通笔记、问题、主张、引用、待办五种类型。
- 笔记可锚定论文、章节和原文片段。
- 笔记可添加到某个综述章节或实验方案。
- 原文、AI 生成内容和用户修改内容分开保存。

### 3.5 综述大纲与草稿

#### 展示位置

Mission 第 4 步；独立路由 `/missions/[missionId]/review`。

#### 页面结构

- 左栏：大纲树，支持主题聚类生成、拖动排序、新增章节。
- 中栏：Markdown/富文本草稿，以章节为单位生成和保存。
- 右栏：本章证据池、引用覆盖率、冲突结论、缺少来源的句子。
- 顶栏：版本、生成范围、导出 Markdown、发送到 Paper Workspace。

#### 实际使用

1. 用户从主题聚类生成大纲候选。
2. 选择某一章节，只基于绑定论文和阅读卡生成该章节草稿。
3. 每个段落保留 `evidence_ids`，点击引用可回到原文片段。
4. 用户修改后保存版本；重新生成只产生提案，不覆盖已确认文本。
5. 完成后发布到 Paper Workspace，生成带 BibTeX key 的 LaTeX 初稿。

### 3.6 实验方案与变量设计

#### 展示位置

Mission 第 5 步；独立路由 `/missions/[missionId]/experiment-plan`。现有 Experiments 页面继续负责执行和指标，不再承担方案设计。

#### 固定结构

| 区块 | 必填内容 |
|---|---|
| 研究问题 | 可证伪的问题陈述 |
| 假设 | H1/H0、依据、支持文献 |
| 数据 | 数据集、版本、样本、划分、泄漏检查 |
| 自变量 | 名称、类型、取值/范围、操纵方式 |
| 因变量 | 指标、单位、方向、统计方式 |
| 控制变量 | 固定条件和理由 |
| 对照与基线 | 论文来源、代码可用性、复现风险 |
| 实验组 | 主实验、基线、消融、敏感性、鲁棒性 |
| 执行计划 | seed、资源、预计时长、预算、停止条件 |
| 分析计划 | 统计检验、置信区间、误差分析、负结果 |
| 决策规则 | 什么结果支持/不支持假设 |
| 风险与伦理 | 数据许可、隐私、偏差和安全 |

#### 关键动作

- “从综述生成方案”：只使用已确认研究空白和阅读卡。
- “检查变量”：检测因变量不可测、控制变量遗漏、数据泄漏和指标方向冲突。
- “生成实验矩阵”：先主实验，再 baseline，再组件消融，最后敏感性。
- “批准并发布”：经用户确认后创建现有 `Experiment` 和预设 `Run`；保留 `plan_version_id`。
- “打开运行面板”：跳转现有 Experiments 页面查看真实进度、日志、指标和产物。

### 3.7 管理中心

#### 展示位置

在“管理”分组增加“管理中心”；路由 `/projects/[projectId]/manage`。

#### 标签页

| 标签页 | 复用/新增 | 主要操作 |
|---|---|---|
| 课题组 | 复用 Organization | 查看课题组、角色、项目数 |
| 研究项目 | 复用 Project | 新建、编辑、归档、查看 Mission |
| 研究人员 | 复用 Organization/Project Membership | 邀请、角色调整、移除、查看归属产物 |
| 文献 | 复用 Paper | 筛选、解析状态、批量重试、删除、来源审计 |
| 实验方案 | 新增 ExperimentPlan | 版本、状态、审批、发布记录 |
| 阅读笔记 | 新增 ReadingNote | 按人员、论文、主题、类型和时间筛选 |

管理中心必须使用与前台相同的业务对象和权限服务，不能再建一套“后台专用假数据”。

## 4. 老师任务要求一一对应

以下编号对应需求文档中的“任务 1—5”。

| 编号 | 老师要求 | 产品中的具体展示位置 | 具体使用方式 | 当前/新增 | 可验收证据 |
|---|---|---|---|---|---|
| T1 | 建设论文知识库，支持标题、摘要、方法、实验、结论、引用和笔记入库检索 | Mission“文献与聚类”、论文详情、管理中心“文献/笔记” | 导入论文 → 分节解析 → 生成 chunk/embedding/关键词索引 → 写笔记 → 混合检索 → 打开引用片段 | Paper/PaperSection 可复用；chunk、embedding、笔记新增 | 搜索同一术语同时返回标题命中、方法段命中和笔记命中；结果可点回原文 |
| T2 | 文献阅读模块自动生成摘要、研究问题、方法流程、优缺点和可复现要点 | 论文详情“阅读卡”页签 | 点击“生成阅读卡” → 查看引用支撑 → 编辑 → 确认 → 加入综述 | Reading Room 可复用；ReadingCard 新增 | 一张阅读卡展示全部固定字段，每条主要结论有来源片段 |
| T3 | 科研 Agent 调用检索、SQL Agent、聚类、综述大纲、实验方案、变量设计、流式语音和引用整理 | Mission 右栏“Agent 轨迹”、各步骤动作、语音浮动入口 | 用户显式触发专项 Agent；查看工具调用与结构化产物；高风险动作需确认 | AgentRun 底座可复用；专项 Agent/工具新增 | 每种 Agent 有一次可回放运行；显示输入、工具、输出、耗时、错误和引用 |
| T4 | 研究前端支持主题输入、文献列表、阅读笔记、综述大纲、实验方案和历史记录 | Mission 列表 + Mission 工作台 5 步 | 输入主题后顺序完成范围、文献、阅读卡、综述、实验方案；时间线查看历史 | 现有页面复用 + Mission 新增 | 从一个 Mission 内可进入全部 6 类界面；刷新或重启后状态仍存在 |
| T5 | 后台支持课题组、项目、研究人员、文献、实验方案和阅读笔记管理 | `/manage`：课题组/项目身份区 + 人员/文献/方案/笔记标签 | 按权限集中查看，并深链到各对象的真实编辑、归档与审计入口 | 组织/项目/成员/文献复用；方案/笔记新增 | 六类对象均为真实持久化数据；权限与前台一致 |

## 5. 老师设计内容要求一一对应

以下编号对应需求文档中的“设计内容/设计要求 1—8”。

| 编号 | 老师要求 | 对应设计 | 具体体现与验收 |
|---|---|---|---|
| D1 | 需求分析：梳理论文检索、阅读笔记、综述生成、实验设计和团队协作流程 | 本文第 0、1、2、3 节 | 产品流程图、页面信息架构、当前缺口审计和对象边界齐全 |
| D2 | 系统架构：文献解析、知识库检索、主题管理、模型服务、Agent 编排和后台接口 | 本文第 7、8、9 节 | 能指出每个模块的输入、输出、服务和数据表；Agent Run 可追踪 |
| D3 | RAG：文本解析、章节切分、向量检索、关键词检索和引用片段展示 | 本文第 7 节 | 混合检索返回带 paper/section/chunk 定位的证据片段；有离线检索测试 |
| D4 | 大模型提示词：摘要、方法归纳、研究空白、综述大纲和实验方案 | 本文第 8 节的 Prompt 合同 | 每个任务使用结构化 schema；引用白名单；无证据内容标记 assumption |
| D5 | Agent：检索、SQL、聚类、阅读卡、综述、实验设计、流式语音、引用整理 | 本文第 8 节专项 Agent 表 | 每个 Agent 都有工具白名单、结构化输出和对应页面，不以名称占位 |
| D6 | 前端：工作台、文献详情、笔记编辑、综述大纲、实验方案和项目空间 | 本文第 2、3 节 | 5 步 Mission 工作台、阅读卡、综述编辑器、方案编辑器和管理中心 |
| D7 | 后台：课题组、项目、人员、文献、方案和笔记等对象管理 | 本文第 3.7、9 节 | 六类对象有 API、分页筛选、权限和审计；管理页不使用假数据 |
| D8 | 系统联调：主题输入到文献组织、综述草稿和实验方案生成 | 本文第 6、10、12 节 | 一条 Demo Mission 可完整演示；产物间保留 version 和 evidence 关系 |

## 6. 端到端流程

```mermaid
flowchart LR
  A["输入研究主题"] --> B["确认范围与纳入标准"]
  B --> C["联邦检索与文献导入"]
  C --> D["全文解析与混合索引"]
  D --> E["主题聚类与文献矩阵"]
  E --> F["阅读卡与锚定笔记"]
  F --> G["研究空白与综述大纲"]
  G --> H["分章节生成综述草稿"]
  H --> I["实验方案与变量设计"]
  I --> J["人工批准"]
  J --> K["发布到 Experiment/Run"]
  K --> L["结果、图表与论文工作台"]
  D -.引用片段.-> F
  F -.证据.-> G
  F -.证据.-> I
  K -.结果锚点.-> L
```

### 6.1 步骤完成条件

| 步骤 | 完成条件 | 下游影响 |
|---|---|---|
| 范围 | 主题、关键词、时间、纳排标准由用户确认 | 允许启动检索 |
| 文献与聚类 | 至少 5 篇纳入论文；解析成功或明确 abstract-only；聚类已确认 | 允许批量阅读卡和大纲 |
| 阅读卡 | 核心论文阅读卡已确认；未确认卡明确标注 | 允许正式综述生成 |
| 综述 | 大纲已确认；草稿无未处理的无来源主张 | 允许生成实验方案 |
| 实验方案 | 变量、对照、指标、数据、决策规则完整；风险检查通过 | 允许发布到实验运行 |

## 7. RAG 设计

### 7.1 当前能力边界

当前 `ResearchAgent` 的工具是外部 `paper.search`、项目 `library.list` 和按论文读取 `paper.sections`。这能做来源受控的问答，但不能被称为完整的论文资料 RAG，因为当前代码没有向量列、chunk 表、embedding pipeline 或跨论文全文混合召回。

### 7.2 增量索引流水线

```text
Paper/PaperSection
  → 清洗并保留 section kind、heading、seq
  → 500–800 token chunk，80–120 token overlap
  → 生成 chunk text hash
  → 写 PostgreSQL FTS（关键词）
  → 调 embedding adapter（向量）
  → 写 pgvector
  → 记录 parser_version / embedding_model / index_status
```

建议新增 `paper_chunks`：

```text
id, project_id, paper_id, section_id
chunk_index, text, token_count, text_hash
section_kind, heading, locator_json
tsv, embedding, embedding_model
parser_version, indexed_at
```

`locator_json` 首期至少含 `section_seq`、`heading`、`char_start`、`char_end`。只有解析器能可靠提供 PDF 页码时才写 `page_number`，不能猜页码。

### 7.3 混合检索

1. 查询理解：提取关键词、领域同义词和筛选条件。
2. 向量召回：Top 40。
3. PostgreSQL FTS/BM25 风格关键词召回：Top 40。
4. Reciprocal Rank Fusion 合并。
5. 可选 reranker 取 Top 12。
6. 按论文和章节做多样性约束，避免结果都来自同一篇论文。
7. 返回 Top 6—10 个引用片段。

返回结构必须包含：

```json
{
  "chunk_id": "...",
  "paper_id": "...",
  "title": "...",
  "section_kind": "method",
  "heading": "Method",
  "snippet": "...",
  "score": 0.82,
  "match_reasons": ["vector", "keyword"],
  "locator": {"section_seq": 3, "char_start": 520, "char_end": 834}
}
```

### 7.4 可见的引用体验

- Agent 回答中的引用显示为 `[P3 · Method]`，不是只显示论文名。
- 点击引用打开右侧证据抽屉，展示片段、章节、匹配原因和“打开论文”。
- 综述段落和实验方案主张保存 `evidence_ids`。
- 删除论文前提示哪些阅读卡、综述段落和实验方案正在引用它。

## 8. Agent 与 Prompt 设计

### 8.1 Agent 不是八个名字，而是八个有边界的工作单元

| Agent/工具 | 输入 | 允许工具 | 结构化输出 | 对应页面 |
|---|---|---|---|---|
| Evidence Agent | scope、关键词、现有库 | 联邦检索、RAG、文献导入建议 | 检索式、候选论文、纳入理由 | 文献与聚类 |
| SQL Agent | 已注册数据集 schema、自然语言问题 | 只读 SQL 预览/执行 | SQL、参数、列、结果摘要、风险 | 实验方案“数据” |
| Cluster Agent | paper embeddings、标题、摘要、阅读卡 | 聚类计算、标签生成 | cluster、成员、标签、解释 | 聚类画布 |
| Reading Card Agent | 指定论文分节 | RAG/section read | 固定 ReadingCard schema + evidence_ids | 论文详情 |
| Review Agent | 已确认聚类、阅读卡、笔记 | RAG、引用整理 | outline 或 section draft | 综述编辑器 |
| Experiment Design Agent | 研究空白、主张、阅读卡 | RAG、数据 schema、基线库 | ExperimentPlan schema | 实验方案编辑器 |
| Voice Research Agent | 音频片段、当前 Mission context | ASR stream、RAG、Research Agent | partial transcript、answer、citations | 全局语音浮层 |
| Citation Agent | 论文集合、草稿引用 | Zotero、BibTeX、DOI 去重 | citation set、缺失字段、冲突项 | 综述/论文 Cite |

### 8.2 SQL Agent 安全边界

- 数据源必须由项目管理员注册，不能连接任意数据库。
- 使用只读数据库账户或只读事务。
- SQL AST 只允许单条 `SELECT`/`WITH ... SELECT`。
- 禁止 DDL、DML、函数写入、跨 schema、文件访问和网络扩展。
- 默认 `LIMIT 200`，超时 5 秒，行数和响应大小受限。
- 先展示 SQL 预览和将访问的表，再由用户执行。
- 保存 query、schema version、执行者、时间、row count 和结果 hash。
- 结果可以形成 ExperimentPlan 的数据证据，但不能被 Agent 改写成不存在的统计结论。

### 8.3 流式语音边界

- 浏览器使用 MediaRecorder/Web Audio 产生短音频分片。
- 音频分片经 WebSocket 发送到可替换 ASR adapter。
- UI 同时显示“临时转写”和“已确认转写”；Agent 只引用已确认或带置信度的文本。
- 语音提问触发带 Mission context 的 Research Agent，回答必须带论文引用。
- 未配置 ASR 时麦克风入口禁用，并显示“需要配置转写服务”；不得把选择音频文件当成已经完成转写。
- 首期不承诺说话人分离和长录音离线处理；这两项可以作为后续增强。

### 8.4 Prompt 合同

所有专项 Prompt 统一为五层：

1. Policy：引用、权限、隐私、不得虚构。
2. Role：阅读卡/综述/实验设计等明确角色。
3. Task：本次具体任务和输出 schema。
4. Context：Mission 范围、论文片段、数据 schema、用户确认项。
5. Output：严格 JSON schema；自然语言只是渲染结果，不是唯一存档。

每次运行记录 `prompt_version`、`model_config_id`、`retrieved_chunk_ids`、`tool_calls` 和 `output_schema_version`。

#### 摘要 Prompt 要点

- 区分作者明确陈述和模型归纳。
- 输出研究问题、方法、数据、结果、局限。
- 每个结论附 evidence_ids。

#### 方法归纳 Prompt 要点

- 输出有顺序的方法步骤，而不是一段泛化描述。
- 提取输入、处理、模型/算法、输出和关键超参数。
- 未给出的实现细节必须写 `unknown`。

#### 研究空白 Prompt 要点

- 区分 coverage gap、method gap、evaluation gap、contradiction。
- 至少给出支持论文和反例论文。
- 输出可证伪研究问题，而不是营销式“创新点”。

#### 综述大纲 Prompt 要点

- 一级标题来自已确认主题聚类。
- 每节声明覆盖论文、核心比较维度和缺失证据。
- 不允许只按论文逐篇罗列。

#### 实验方案 Prompt 要点

- 研究问题、变量、对照、指标、数据和决策规则必须齐全。
- baseline 必须绑定论文或标记“待验证建议”。
- 明确预算、停止条件、复现和负结果记录。

## 9. 数据、服务与 API

### 9.1 建议新增的核心对象

| 对象 | 关键字段 | 复用关系 |
|---|---|---|
| `ResearchMission` | topic、scope_json、status、current_step、owner、version | 属于 Project；关联 AgentRun |
| `MissionStep` | step_type、status、input_version、output_version、approved_by | Mission 的可恢复状态 |
| `PaperChunk` | text、section locator、tsv、embedding、index metadata | 属于 Paper/PaperSection |
| `TopicCluster` | name、description、version、algorithm、status | 属于 Mission |
| `TopicClusterPaper` | cluster_id、paper_id、score、position、manual_override | 聚类成员 |
| `ReadingCard` | summary、question、method_flow、pros/cons、reproducibility、evidence | Mission + Paper；带版本 |
| `ReadingNote` | note_type、content、paper/section/chunk anchor、author | Mission 可选；Paper 可选 |
| `ReviewDraft` | outline_json、status、current_version | 属于 Mission |
| `ReviewSectionVersion` | section_key、content、evidence_ids、author_type、version | 可审阅生成 |
| `ExperimentPlan` | question、hypotheses、datasets、variables、groups、metrics、decision_rule、budget | 属于 Mission/Idea；可发布 Experiment |
| `CitationCollection` | name、style、status | Mission/Review 共用 |
| `ResearchDataset` | name、connection_ref、schema_snapshot、permission | SQL Agent 数据源 |
| `VoiceSession` | transcript、confidence、started_by、status | 属于 Mission；关联 AgentRun |

### 9.2 版本与溯源

- Mission 每个步骤保存 `input_snapshot_hash` 和 `output_version`。
- 阅读卡、综述、实验方案均不能原地覆盖历史版本。
- AI 生成、用户编辑和系统导入分别记录 `author_type`。
- 产物关系使用 `MissionArtifactLink` 或统一 provenance edge 表表达：

```text
PaperChunk → ReadingCard claim
ReadingCard → ReviewSection
ReviewSection gap → ExperimentPlan hypothesis
ExperimentPlan version → Experiment / Run
Run metric → ResultAnchor → Paper Workspace
```

### 9.3 API 草案

```text
POST   /projects/{project_id}/missions
GET    /projects/{project_id}/missions
GET    /projects/{project_id}/missions/{mission_id}
PATCH  /projects/{project_id}/missions/{mission_id}
POST   /projects/{project_id}/missions/{mission_id}/steps/{step}/approve
GET    /projects/{project_id}/missions/{mission_id}/timeline

POST   /projects/{project_id}/missions/{mission_id}/discover
POST   /projects/{project_id}/missions/{mission_id}/cluster
PATCH  /projects/{project_id}/missions/{mission_id}/clusters/{cluster_id}

POST   /projects/{project_id}/papers/{paper_id}/reading-cards
GET    /projects/{project_id}/papers/{paper_id}/reading-cards
POST   /projects/{project_id}/reading-notes
PATCH  /projects/{project_id}/reading-notes/{note_id}
DELETE /projects/{project_id}/reading-notes/{note_id}

POST   /projects/{project_id}/missions/{mission_id}/review/outline
POST   /projects/{project_id}/missions/{mission_id}/review/sections/{section_key}/generate
PUT    /projects/{project_id}/missions/{mission_id}/review/sections/{section_key}
GET    /projects/{project_id}/missions/{mission_id}/review/versions

POST   /projects/{project_id}/missions/{mission_id}/experiment-plans/generate
PUT    /projects/{project_id}/experiment-plans/{plan_id}
POST   /projects/{project_id}/experiment-plans/{plan_id}/validate
POST   /projects/{project_id}/experiment-plans/{plan_id}/approve
POST   /projects/{project_id}/experiment-plans/{plan_id}/publish

POST   /projects/{project_id}/rag/search
POST   /projects/{project_id}/datasets/{dataset_id}/sql/preview
POST   /projects/{project_id}/datasets/{dataset_id}/sql/execute
WS     /ws/projects/{project_id}/voice-sessions/{session_id}
```

### 9.4 权限

| 操作 | Viewer | Researcher | Project Admin | Org Admin |
|---|---:|---:|---:|---:|
| 查看 Mission/论文/阅读卡 | 是 | 是 | 是 | 是 |
| 新建 Mission、笔记、草稿 | 否 | 是 | 是 | 是 |
| 批准步骤/发布实验 | 否 | 可配置 | 是 | 是 |
| 注册 SQL 数据源 | 否 | 否 | 是 | 是 |
| 管理成员与角色 | 否 | 否 | 项目范围 | 组织范围 |
| 删除/归档业务对象 | 否 | 自己的草稿 | 是 | 是 |

### 9.5 CLI / Harness 对应入口

网页和终端必须调用同一套 Mission API、权限、乐观版本控制和审计时间线。正式命令使用复数 `missions`，避免与早期仅保存在本地的单 Coordinator `mission` 骨架混淆：

```bash
researchos missions create "研究主题" --objective "预期产物" --scope-json @scope.json
researchos missions list
researchos missions show <mission-id>
researchos missions update <mission-id> --status paused
researchos missions step-save <mission-id> literature --output-json @literature.json --status needs_review
researchos missions approve <mission-id> literature --note "人工复核说明"
researchos missions timeline <mission-id>
researchos missions generate-card <mission-id> <paper-id> --regenerate
researchos missions card-versions <mission-id> <paper-id>
researchos missions review-outline <mission-id>
researchos missions review-generate <mission-id> <section-id> --regenerate
researchos missions review-save <mission-id> <section-id> --body-file section.md
researchos missions review-versions <mission-id>
researchos missions plan-generate <mission-id>
researchos missions plan-save <mission-id> --file experiment-plan.json
researchos missions plan-publish <mission-id>
researchos missions plan-versions <mission-id>
```

CLI 未显式传 `--version` 时会先读取远端最新版本；若页面或另一个终端已修改，同样返回版本冲突，不允许静默覆盖。结构化 JSON 既可内联，也可使用 `@文件路径`，便于后续 Agent/Harness 将主题聚类、阅读卡、综述大纲和实验方案作为可审计产物提交。

## 10. 历史记录与具体展示

老师要求“历史记录”，必须展示业务历史而不只是后台日志。

Mission 右栏时间线应包含：

- 谁在何时创建/修改/批准了范围。
- 检索用了哪些查询和来源，导入了哪些论文。
- 哪次聚类产生了什么版本，用户怎样调整。
- 哪些阅读卡由 AI 生成、由谁修改和确认。
- 综述大纲和章节的版本差异。
- 实验方案的校验、审批和发布。
- 关联的 Agent Run、工具调用、错误和重试。
- 哪个 Experiment/Run 来源于哪个 plan version。

默认显示业务摘要；展开后才显示工具参数和技术日志，避免把主页面做成调试控制台。

## 11. UI 状态和设计质量

### 11.1 必须覆盖的状态

- Loading：按最终布局显示 skeleton，不只放全屏 spinner。
- Empty：告诉用户下一步能做什么，并给真实入口。
- Partial：某些论文解析失败时允许继续，但明确 abstract-only。
- Error：内联错误、错误原因、重试和保留已有结果。
- Stale：上游论文/阅读卡变化后，下游综述和方案显示过期提示。
- Conflict：多人编辑时显示版本冲突并允许对比，不静默覆盖。
- Permission：解释为什么无权操作以及需要的角色。
- Provider unavailable：LLM/embedding/ASR/外部检索不可用时显示精确降级状态。

### 11.2 视觉层级

- Mission 页面以“步骤和产物”为主，不再新增一排同权重卡片。
- 颜色只承担状态含义：进行中、待确认、完成、错误、过期。
- 数据和版本号使用 tabular numbers/等宽字体。
- 阅读正文限制行宽；证据片段与用户笔记在表面层级上明显区分。
- 主要动作每个页面最多一个；重新生成、导出等使用次级或文字动作。
- 支持键盘焦点、无障碍标签、减少动画偏好和中英文文案。

## 12. 四周增量实施路线

### 第 1 周：主线可见与数据骨架

目标：先让老师能看到完整流程位置，并且每一步有真实状态。

- 新增 ResearchMission/MissionStep/MissionArtifactLink 及迁移。
- 新增 Mission 列表和 5 步工作台壳层。
- 将现有 Research、Reading Room、Experiments、Paper Workspace 深链接接入。
- 新增 ReadingNote CRUD 和论文详情笔记栏。
- 增加管理中心壳层，复用组织/项目/成员/文献 API。
- 增加 Teacher Demo 项目和至少 8 篇可解析论文数据。

验收：输入主题后能创建 Mission；刷新后步骤、论文和历史不丢失。

### 第 2 周：知识库、RAG、阅读卡和聚类

- 新增 `paper_chunks`、FTS、pgvector、embedding adapter 和索引任务。
- 实现混合检索 API 与引用片段抽屉。
- 新增 ReadingCard schema、生成/编辑/确认流程。
- 实现可重复主题聚类、标签生成和人工调整。
- 对外部 provider/embedding 失败设计降级和重试。

验收：同一问题可从标题、方法段、结论段和笔记中检索；阅读卡每条结论能回到证据。

### 第 3 周：综述与实验设计 Agent

- 新增 ReviewDraft/SectionVersion 与大纲树。
- 实现按章节、按证据生成综述草稿和引用覆盖检查。
- 新增 ExperimentPlan schema、变量编辑器、方案校验器。
- 新增 Experiment Design Agent；批准后发布到现有 Experiment/Run。
- 新增 Citation Agent，打通 Zotero/BibTeX/Paper Workspace。

验收：主题聚类可生成大纲；大纲可生成带引用的段落；研究空白可生成结构化实验方案并发布到实验页。

### 第 4 周：SQL、语音、后台联调与演示质量

- 实现只读 SQL Agent、schema 浏览、查询预览和审计。
- 接入一个真实 ASR adapter，完成短语音流式转写与带引用回答；未配置时明确禁用。
- 完成管理中心六类对象的统一页面与真实编辑入口。
- 补 Mission 时间线、stale 传播、权限和错误状态。
- 补 E2E、API 测试、RAG 离线评测集和 Teacher Demo 演示数据。
- 固化演示脚本和截图清单。

验收：老师文档中的 T1—T5、D1—D8 每一条都能指出页面、操作、后端对象和可重复验收证据。

## 13. 演示脚本

### 13.1 Demo 数据

新增项目 `Teacher Demo · Literature to Experiment`，包含：

- 8—12 篇同主题论文，至少 5 篇有可解析分节全文。
- 2—3 个稳定主题聚类。
- 5 张已确认阅读卡和 3 条不同类型的阅读笔记。
- 1 份有 3 个一级章节的综述大纲。
- 1 个带引用的综述章节草稿。
- 1 份包含自变量、因变量、控制变量、对照组和决策规则的实验方案。
- 1 个从该方案发布的 Experiment，至少 2 个 Run。
- 1 次失败/重试记录，用于展示错误和历史，而不是只展示完美路径。

### 13.2 8 分钟演示顺序

1. 在“科研任务”输入主题并打开已准备好的 Demo Mission。
2. 展示范围和纳入标准，进入文献步骤。
3. 展示文献列表、主题聚类和论文对比矩阵。
4. 搜索一个方法问题，打开引用片段，证明 RAG 不是只返回标题。
5. 打开一篇论文的阅读卡和锚定笔记。
6. 从聚类生成综述大纲，打开一个带引用的草稿段落。
7. 从研究空白生成实验方案，展示变量、对照、指标和风险检查。
8. 批准并发布到 Experiments，打开真实 Run 指标和日志。
9. 打开 Mission 历史，展示 Agent 工具调用、版本和上下游关系。
10. 最后打开管理中心，展示课题组、人员、文献、方案和笔记管理。

### 13.3 必拍展示图

1. 科研任务 5 步工作台全景。
2. 文献聚类 + 对比矩阵。
3. RAG 引用片段抽屉。
4. 论文阅读卡 + 锚定笔记。
5. 综述大纲 + 引用覆盖率。
6. 实验方案变量表 + 校验结果。
7. 管理中心六类真实对象。
8. Mission 历史与 Agent 工具调用。

## 14. 验收标准

### 14.1 功能验收

- T1—T5、D1—D8 的每一项都能在 UI 中找到固定入口。
- 从主题创建的 Mission 在服务重启后可以恢复。
- 文献检索结果能打开章节级引用片段。
- 阅读卡固定字段齐全；主要结论都有 evidence_ids。
- 综述草稿不存在无法定位来源却被当作事实的引用。
- 实验方案存在可编辑变量、对照、指标和决策规则。
- Experiment/Run 能追溯到 plan version。
- 管理中心的所有列表来自真实 API。
- SQL Agent 无法执行写操作或访问未注册 schema。
- 未配置 ASR 时不会显示“转写成功”。

### 14.2 测试验收

- API：Mission 状态、版本冲突、权限、stale 传播、发布实验。
- RAG：chunk 定位、关键词/向量融合、项目隔离、引用白名单。
- Agent：结构化 schema、工具白名单、无效引用过滤、失败重试。
- SQL：SELECT allowlist、超时、LIMIT、跨项目数据源隔离。
- 前端 E2E：创建 Mission → 导入论文 → 确认阅读卡 → 生成大纲 → 生成并发布实验方案。
- 可访问性：键盘完成主流程、焦点可见、表单标签和错误提示可读。

### 14.3 产品验收

- 新用户不需要理解现有 12 个模块，也能从一个主题开始。
- 老师不需要听口头解释，就能从页面看出每项要求在哪里体现。
- 每个 AI 结果都能回答“根据什么生成、由哪个 Agent 生成、用户是否确认”。
- 系统在 Provider 失败、解析不完整和数据不足时诚实降级。

## 15. 首期明确不做

以下内容不影响完成老师要求的首期闭环，但必须避免伪装成已经具备：

- 全自动无人值守研究和自动投稿。
- 不受限的任意数据库 SQL 执行。
- 长录音说话人分离、会议级 ASR 和音频永久存储治理。
- 可靠 PDF 页码定位、图表/公式跨模态 RAG（首期使用章节和字符锚点）。
- 自动执行付费、大规模或远程实验。
- 多人 CRDT 实时共同编辑。

这些能力以后可在现有 Mission、provenance、权限和审批机制上继续增加，不需要推翻本设计。
