# 老师要求逐项验收矩阵

> 对齐文档：《科学文献研究智能体：从综述到实验设计》
> 验收版本：2026-08-06 增量实现
> 原则：每项同时给出“页面入口、真实操作、后端对象、可复跑证据”，不以静态占位页作为完成依据。

## 一、老师提出的产品能力 T1—T5

| 编号 | 要求 | 页面中在哪里体现 | 现场如何使用 | 真实后端与持久化 | 可复跑验收证据 |
|---|---|---|---|---|---|
| T1 | 可检索论文知识库：标题、摘要、方法、实验、结论、引用、笔记 | “科研任务 → 文献与聚类”的论文集、混合证据检索；论文 Reading Room；“管理中心 → 文献/笔记” | 把项目论文纳入 Mission，系统按章节生成 chunk 与向量/关键词索引；搜索方法问题，结果显示论文、章节、原文片段；进入论文写锚定笔记 | `Paper`、`PaperSection`、`PaperChunk`、`MissionPaper`、`ReadingNote`；`POST /rag/search`；迁移 `0011/0012` | `test_vector_indexing.py` 检查 chunk 定位、确定性向量与融合；Demo 有 8 篇论文、method/results 章节及索引 |
| T2 | 阅读模块：摘要、研究问题、方法流程、优缺点、复现要点 | “科研任务 → 阅读卡”；论文 Reading Room 的阅读卡和章节笔记 | 对某篇论文点击生成阅读卡，等待 Agent Run；查看固定字段和原文证据；人工修改并确认；历史版本可回看 | `ReadingCard`、`ReadingCardVersion`、`ReadingNote`；`reading_card` Agent；迁移 `0011/0013` | 无效 section UUID 或不匹配引句不会成为已证实主张；Demo 预置 8 张已复核阅读卡与 3 条锚定笔记 |
| T3 | 科研 Agent：文献检索、SQL、主题聚类、综述、实验设计/变量、流式语音、引用整理 | Mission 各阶段动作与右侧运行轨迹；`/data-query`；`/review`；`/experiment-plan`；`/citations`；Research Inbox 流式语音 | 显式触发专项 Agent；生成结果先进入待复核；SQL 只查询注册快照；综述主张回到原文；实验门禁通过后发布；语音临时结果实时进入文本；引用审计导出 BibTeX | `AgentRun/ToolCall/Event`；`reading_card`、`review_section`、`experiment_planner`、`sql_analyst`、`citation_organizer`；浏览器 `SpeechRecognition` | Agent 输入、状态、错误和输出均持久化；`test_data_lab.py` 证明写 SQL/多语句/系统表被拒绝；E2E 检查全部固定入口 |
| T4 | 前端：主题、论文列表、笔记、综述大纲、实验方案、历史 | `/missions` 与五阶段 `/missions/[missionId]`，以及 Review、ExperimentPlan 专用编辑器 | 输入主题创建 Mission；逐步确认范围、文献、阅读卡、综述、实验方案；刷新后恢复；时间线查看生成、编辑、确认和发布 | `ResearchMission`、`MissionStep`、`MissionEvent` 及各产物 version 表；迁移 `0010—0018` | 前端 production build 通过；`mission-requirements.spec.ts` 从 Demo 项目逐页验证主链路 |
| T5 | 后台：课题组、项目、研究人员、文献、方案、笔记 | `/projects/[projectId]/manage`，侧栏“管理中心” | 在一个页面切换研究人员、文献、实验方案和笔记；页头显示组织与项目；具体编辑跳转现有真实工作区 | `GET /projects/{id}/manage/summary` 聚合 `Organization/Project/ProjectMembership/User/Paper/ExperimentPlan/ReadingNote` | 页面不生成后台专用假数据；每行来自当前项目真实查询并使用原权限服务 |

## 二、老师提出的开发内容 D1—D8

| 编号 | 要求 | 代码/文档落点 | 验收结论 |
|---|---|---|---|
| D1 | 需求与业务流程分析 | `TEACHER_REQUIREMENTS_INCREMENTAL_PRODUCT_DESIGN_ZH.md` 第 0—5 节 | 已给出现状审计、增量边界、信息架构、页面操作和 T1—T5 对应表 |
| D2 | 系统与数据架构设计 | 设计文档第 6、9 节；`missions/`、`knowledge/`、`reviews/`、`experiment_plans/` 等模块 | 五阶段 Mission 是聚合主线，专业模块保持边界；迁移 `0010—0018` 为单一连续链 |
| D3 | RAG：解析、切分、向量、关键词、引用片段 | `research/ingest.py`、`knowledge/indexing.py`、`knowledge/service.py`、Mission 文献阶段；实现细节见 `BLOCK_A_RAG_DELIVERY_ZH.md` | PostgreSQL FTS + pgvector HNSW 混合召回，RRF 融合（v2）；双 embedding profile 统一 1024 维：百炼 text-embedding-v4（在线）+ 确定性 hashing（离线 CI 可复现）；结果带 paper/section/chunk 定位与 match_reasons |
| D4 | 大模型提示词与结构化输出 | `agents/runtime/*_agent.py` 与 `agents/llm/mock.py` | 阅读卡、章节综述、实验方案、SQL、引用均使用结构化 schema；综述/基线证据经过 UUID 与原文引句白名单校验 |
| D5 | 多类专项 Agent | AgentType 与五个专项 runtime；主题聚类为确定性服务 | 每种产物有真实运行入口、AgentRun、持久化输出和人工复核状态，不只是菜单名称 |
| D6 | 研究前端 | `features/missions/`、Reading Room、Research Inbox、Management Workspace | 主题到实验方案的主线及所有教师要求入口已可见；中英文主界面、加载/空/错误/冲突状态沿用现有设计系统 |
| D7 | 后端、管理与权限 | FastAPI routers/services/models；`management/`；项目角色检查 | API 使用同一项目访问控制；SQL 数据源、Mission 和产物都做项目归属校验；OpenAPI 可生成 |
| D8 | 联调、测试与演示 | `seed/demo.py`、`scripts/site.ps1`、API unit/integration tests、全套 Playwright E2E | pgvector Docker 数据库、迁移、幂等 seed、后台 Worker、16 条 API 冒烟与 8 条浏览器链路均已实机复跑；production build 与静态质量门通过 |

## 三、8 分钟现场演示路径

1. 以 `demo@researchos.dev` / `demo-password-123` 登录，打开侧栏“科研任务”。
2. 打开字段为 `Document AI / Low-resource learning` 的 Demo Mission，展示五阶段、80% 进度和时间线。
3. 在“文献与聚类”展示 8 篇明确标识为 Demo 的论文、3 个主题簇；做一次跨论文证据检索并展开 method/results 原文片段。
4. 在“阅读卡”展示摘要、问题、方法流程、优缺点、复现要点和已校验引句；再从论文页面展示锚定笔记。
5. 打开“综述”，展示章节树、引用覆盖率、主张—证据审计和不可变版本。
6. 打开“实验方案”，展示自/因/控制变量、证据基线、数据切分、主指标、矩阵、决策规则、停止条件、风险和发布门禁。
7. 打开 Data Lab，对 `Demo experiment metrics` 提问；展示生成 SQL、只读说明、表格结果和历史。
8. 打开“引用审计”展示缺失字段、重复项与 BibTeX；到 Research Inbox 展示实时语音转写；最后用“管理中心”展示人员、文献、方案和笔记均来自真实数据。

## 四、可重复验证命令

```powershell
# 一条命令启动可审核网站（Docker 基础设施 + 本机代码服务）
pnpm site:up
pnpm site:verify

# API：完整 PostgreSQL/pgvector + Redis 集成套件
cd apps/api
$env:POSTGRES_DSN='postgresql+asyncpg://researchos:researchos@localhost:55432/researchos_test'
$env:REDIS_URL='redis://localhost:56379/15'
$env:DB_USE_NULLPOOL='true'
uv run pytest tests -q
uv run ruff check researchos tests
uv run mypy researchos

# Web：类型、生产构建和真实浏览器 E2E
cd ../web
pnpm typecheck
pnpm build
pnpm exec playwright test
```

本机普通 PostgreSQL 不需要安装扩展。快速启动器使用 `pgvector/pgvector:pg16` 镜像，并把数据库与 Redis 分别映射到 `55432`、`56379`，避免占用常见的 `5432`、`6379`。迁移和 Demo seed 会在每次 `site:up` 时幂等执行。

### 2026-08-07 实机结果

- `pnpm site:verify`：16 passed / 0 failed。
- Playwright：8 passed，包含设计系统、完整旧版 smoke 与老师要求主链截图。
- API：398 passed / 1 skipped（可选依赖）/ 0 failed；使用真实 PostgreSQL/pgvector 与 Redis，全量耗时 307.97 秒。
- Ruff：通过；mypy：267 个源文件通过；Next.js production build：通过，包含 Mission、Review、ExperimentPlan、Data Lab、Citation、Management 等全部路由。

## 五、诚实边界

- Demo 论文全部带 `not_a_real_publication` 元数据，只用于演示数据结构和操作流程，不能作为科学证据。
- 流式语音使用 Chrome/Edge 浏览器的实时识别能力；不支持的浏览器明确提示降级，不保存原始音频，也不声称具备会议级说话人分离。
- SQL Agent 不连接任意生产数据库，只查询用户显式注册的 JSON 快照；这是首版有意设置的安全边界。
- hashing embedding 用于离线可复现与完整链路验证，可通过既有 adapter 增量替换为语义 embedding provider。
