# ResearchOS 三阶段演进路线图 (v1 → v2 → v3)

> 状态：思考文档。v1 = 当前基线，v2 = 深化细节，v3 = Harness 部署 + 完整体验。

---

## 🏔️ v1 — 可用骨架（当前状态）

**时间：2026.07 — 现在**

v1 完成了"像素级可验证"的基础设施：38 张数据库表、5 个核心工作台、Agent 运行时、真实 CLI、
Docker Compose 全栈部署、CI 质量门。

### 已完成

| 系统 | 内容 |
|---|---|
| **API** | FastAPI + Celery + PostgreSQL/pgvector + Redis + MinIO。38 张迁移表，完整 auth/org/project 多租户 |
| **前端** | Next.js 15 + Monaco + Recharts + Tailwind。5 个工作台全部渲染 |
| **Agent Runtime** | Coordinator + 4 专项 Agent（Research/Coding/Experiment/Paper），handoff 协议，tool-call 记录 |
| **CLI** | `researchos init/login/ask/chat/runs/context/memory/mission`，真实 API 调用 |
| **DevOps** | Docker Compose、CI（lint+test+typecheck+build）、PowerShell 脚本、smoke test |
| **Reviewer Arena** | venue 选择、模拟审稿、证据缺口标记 |
| **CCFDDL** | 中文 iCal 搜索/筛选/订阅 |
| **文档** | 产品蓝图、Agent 协议、Harness 架构指南、能力 TODO |

### v1 的体验问题

- 前端和 API 都能跑，但 **Mock LLM 返回固定内容**，没有真智能感
- **缺少 Redis/MinIO 时 `/readyz` 503**，首次启动容易困惑
- 前端是骨架 UI，**交互不够流畅**，错误/空状态覆盖不完整
- Harness CLI 可以对话但 **不能真正执行代码**（终端仅 local 白名单命令）
- **没有持久化 Mission**：关掉浏览器/CLI，任务就断了

---

## 🧗 v2 — 流程深化 + Harness 内容充实（下一步）

**目标：每一步流程都走通真数据，Harness 从"概念"变成"可感知的能力"。**

### 2.1 系统体验（System Experience）

体验不是 UI 换皮肤——是让研究员在每个时刻都知道：

> 系统在做什么、为什么这么做、下一步可以做什么、当前有什么风险。

#### 具体方向

1. **全局状态栏 / 仪表盘**
   - 打开 ResearchOS 第一眼看到：活跃 Mission 数量、等待审批的 Patch、本周实验进度、即将到来的 DDL
   - 不做"数据报表"，而是 **可操作的待办清单 + 上下文卡片**
   - 每张卡片可点击直达对应工作台

2. **进度可视化与暂停/恢复**
   - Agent Run 展示阶段（planning → executing → reviewing → done）
   - 每个阶段有耗时、token 消耗、中间产物预览
   - 支持暂停检查点 → 人工确认 → 继续

3. **智能通知**
   - 实验跑完/审稿返回/DDL 临近 → 桌面通知 + 邮件 digest
   - 通知内容可操作："实验精度提升 2.3% → 查看对比 → 更新论文"

4. **错误/空状态的叙事化**
   - 不是"Error 500"，而是"数据库连接失败，可能原因：...，建议：..."
   - 空列表不说"No data"，而是"还没有实验——创建一个实验来追踪你的研究"

5. **中英文切换的深度覆盖**
   - 不仅是 UI 标签，而是错误消息、Agent 输出、论文模板都双语
   - 中文输入 → 中文论文模板，英文会议 → 自动切换英文写作

### 2.2 核心算法与数据分析

ResearchOS 的数据价值在于"连接"——连接论文、实验、代码、审稿意见。

#### 具体方向

1. **论文推荐与匹配**
   - 不是简单 TF-IDF，而是 **项目级语义画像 + 引用图谱 PageRank + 时间衰减**
   - "这个论文和你当前实验的相关度是 87%，因为：用了同样的数据集 X，对比了同样的 baseline Y"
   - 推荐理由可解释、可点击验证

2. **实验智能对比**
   - 自动识别两个实验的差异：dataset split / hyperparameter / architecture change
   - 生成对比报告：哪个维度变了、变化方向、影响大小
   - 不是简单 diff，是 **实验维度的因果推断**

3. **审稿意见聚类与优先级**
   - 多个 reviewer 意见 → 聚类为"必须改 / 建议改 / 澄清即可"
   - 同一类意见合并为一个 action item，避免重复修改
   - 修改完成后自动生成 Response Letter 骨架

4. **研究缺口检测**
   - 从论文集合中提取 Claim graph → 找"没人做过的边"
   - 给出缺口卡片：假设、需要的实验、预估成本、风险等级
   - 不做"AI 自动想 idea"，而是"AI 帮你标注哪里没人去过"

5. **引用图谱可视化**
   - Paper → Claim → Evidence → Run → Artifact → Commit
   - 点击任一条论文结论，看到它依赖的所有实验和代码
   - 修改实验后自动标记受影响论文段落

### 2.3 Workflow 引擎深化

当前 Agent 协议有 handoff，但缺少"可恢复的多步骤任务"。

#### 具体方向

1. **Mission DAG 定义**
   ```
   Research Mission: "复现 Paper X 的核心实验并与我们的方法对比"
   ├── Task 1: 解析 Paper X 实验配置 (Agent: Research)
   ├── Task 2: 搭建 baseline 代码环境 (Agent: Coding)
   ├── Task 3: 运行 baseline 实验 (Agent: Experiment) ── 依赖 Task 1,2
   ├── Task 4: 运行我们的方法 (Agent: Experiment) ── 依赖 Task 2
   ├── Task 5: 对比分析 (Agent: Research) ── 依赖 Task 3,4
   └── Task 6: 更新论文 (Agent: Paper) ── 依赖 Task 5
   ```
   - 每个 Task 有输入 schema、输出 schema、超时、重试策略、人工审批点
   - DAG 可以在浏览器里拖拽编辑

2. **Checkpoint / Resume**
   - 每个 Task 完成后写 checkpoint 到 DB
   - 进程崩溃 / 服务重启后自动 resume
   - 不是"从头再来一遍"

3. **人工闸门（Human-in-the-loop）**
   - 关键节点自动暂停 → 通知研究员 → 审批/修改 → 继续
   - 闸门定义：哪些 Task 必须人工确认、默认超时后怎么办
   - 审批记录永久保存，每个决策可追溯

4. **Workflow 模板市场**
   - "复现实验"、"写 intro"、"投稿前检查清单"等预置模板
   - 模板参数化，填入项目变量即可运行
   - 用户自定义模板可分享给团队成员

### 2.4 Harness 内容充实

Harness 不是"能调用 LLM"，而是"LLM 运行时有结构化的约束和上下文"。

#### 具体方向

1. **Skill 体系化**
   - 不是"写一个 prompt"，而是 `SKILL.md + manifest + scripts + references + tests`
   - 每个 Skill 有明确的：输入/输出/权限/依赖/评测集/版本
   - "论文写作 Skill"包含：LaTeX 模板、常用 phrase bank、审稿人常见问题避坑指南
   - "实验 Skill"包含：常见 hyperparameter 范围、早停策略、日志格式规范

2. **System Prompt 分层**
   ```
   Layer 1: Harness Policy（不变）—— 安全边界、输出规范、禁止行为
   Layer 2: Role（按 Task 切换）—— 研究员/编码者/审稿人/写作者
   Layer 3: Skill（按需要加载）—— 论文写作 Skill / 实验设计 Skill / 审稿 Skill
   Layer 4: Task（当前任务描述）—— 具体的输入、期望输出、约束
   Layer 5: Context（动态填充）—— 相关论文片段、实验日志、对话历史
   ```
   - 每次 Agent Run 记录各层 hash，问题可追溯到"哪个 prompt 版本导致"

3. **上下文工程**
   - 不是把整个聊天历史塞进去
   - 压缩为结构化格式：Goal / Decisions Made / Evidence Found / Open Questions / Next Steps
   - 压缩前后可对比，防止重要信息丢失
   - 支持研究员手动编辑/补充压缩后的上下文

4. **记忆系统**
   - 项目级记忆：项目目标、关键论文、实验配置、已尝试方向
   - 研究员记忆：偏好（写作风格、模型选择）、常用 Skill、历史决策
   - 记忆自动衰减和清理：超过 N 天未引用的记忆自动归档
   - 研究员可查看、编辑、删除任何记忆

5. **评测体系**
   - 每个 Skill 绑定固定评测集（任务 + 期望输出 + 评分维度）
   - LLM Judge 自动打分 + 人工抽检
   - 分数低于阈值 → 自动回滚到上一个已知好的版本
   - 评测结果可视化在 Skill 管理页面

---

## 🚀 v3 — Harness 完整部署 + 放松体验（ReLax）

**目标：Harness 成为真正的"科研操作系统"，每天开机就打开它。**

### 3.1 Harness 完整部署

v2 在 local 跑，v3 把 Control Plane 部署到服务器，真正实现"关了电脑任务还在跑"。

#### 具体方向

1. **Server Lab**
   - 一台 Linux 服务器（或 GPU 集群）运行 ResearchOS Control Plane
   - 研究员通过 Web/CLI 提交 Mission，浏览器关了任务继续
   - SSH/Slurm 集成：可以分发任务到计算节点

2. **Durable Execution**
   - Mission 提交后持久化到 PostgreSQL/RabbitMQ
   - 服务重启/升级时，正在运行的 Task 自动恢复
   - 执行日志流式推送，研究员随时查看进度

3. **GPU 感知调度**
   - 根据 GPU 显存/利用率自动调度实验
   - 低优先级实验自动让出 GPU 给高优先级
   - 空闲 GPU 自动跑 baseline / ablation
   - 实验排队可视化：等待队列、预计开始时间、预计耗时

4. **容器隔离**
   - 每个实验跑在独立容器（Docker / gVisor）
   - GPU 显存/算力配额、网络白名单、磁盘配额
   - 任意代码执行在沙箱内，不能越界

5. **多用户协作**
   - 团队共享 GPU 池
   - 成员权限：Owner / Admin / Member / Viewer
   - 实验按优先级 + deadline + 公平份额调度
   - 协作论文：CRDT 实时编辑 + Git 版本控制

### 3.2 体验"升级"（ReLax）

v3 的目标不只是"能用"——而是"用着舒服，像呼吸一样自然"。

#### 具体方向

1. **开机即用**
   - 打开 ResearchOS → 自动恢复上次会话
   - 实验面板实时显示 GPU 状态（挂了多少任务、用了多少显存）
   - DDL 面板自动标记"离投稿还有 X 天，你还差 Y 个实验"

2. **语音交互**
   - "Rho，帮我看看昨天那个实验跑完了没有" → 语音查询
   - "Rho，把这个结果写到论文第三段" → 语音指令
   - 会议录音 → 自动转录 → 提取 Action Items → 创建 Mission

3. **移动端**
   - 手机查看实验进度、审批关键节点
   - 推送通知：实验跑完/误差/审稿意见
   - 最小可操作界面：审批/暂停/查看结果

4. **可访问性**
   - 键盘完整操作（不仅是鼠标）
   - 屏幕阅读器支持
   - 高对比度模式

5. **研究松弛感**
   - 不只是生产工具，还有"研究伙伴"的感觉
   - Rho（小獭）不只是吉祥物，而是真的有交互：实验成功时庆祝、失败时鼓励、DDL 临近时提醒
   - "仪式感"功能：每天早晨自动生成"今日研究简报"、每周生成"本周研究周报"
   - 可以"跟 Rho 聊聊天"来澄清研究想法（rubber duck debugging）

---

## 🧠 发散思考：还有哪些方向值得探索

### 学术社交方向

- **"别人的实验"**：可以看到公开项目用了什么配置、跑了多久、结果如何
- **审稿人匹配**：根据你的 expertise 推荐审稿机会
- **合作者推荐**：在相邻领域找可能需要你 skill set 的研究者

### 自动化方向

- **Continuous Research**：像 CI 一样，代码 push 就自动跑 baseline 实验，结果变更自动更新论文图表
- **Self-Improving Agent**：Agent 执行记录 → 分析失败模式 → 自动优化 prompt/skill/策略
- **AutoML for Research**：自动搜索最佳超参、自动选择 baseline、自动做消融实验

### 出版方向

- **一键投稿**：检查所有 venue 要求 → 生成投稿包 → 提交
- **预印本管理**：多版本预印本追踪、版本 diff、引用计数监控
- **会议旅行规划**：DDL + 会议日期 + 机票酒店一站式

### 教育方向

- **"如何做研究"教学模块**：不是教知识点，是教研究方法和工具使用
- **论文阅读俱乐部**：团队共读论文、标注、讨论 → 自动生成 summary
- **新手上路向导**：30 天从零到第一篇论文的引导

---

## 📊 优先级矩阵

选取标准：**在最短时间内让研究员感受到最大价值。**

| 优先级 | v2 方向 | 为什么 |
|---|---|---|
| 🔴 P0 | 真 LLM 接入（Anthropic/OpenAI） | 没有真智能，一切都是假的 |
| 🔴 P0 | Mission 持久化 + Resume | Agent Run 断了要重来 → 无法信任 |
| 🟡 P1 | Skill 体系化（5-10 个核心 Skill） | 让 Agent 输出质量可预期 |
| 🟡 P1 | 进度可视化 + 实验对比 | 研究员最常做的事情 |
| 🟡 P1 | 上下文压缩 | 减少 token 消耗，提高长对话质量 |
| 🟢 P2 | Workflow 模板 | 降低使用门槛 |
| 🟢 P2 | 审稿意见聚类 | 投稿季杀手功能 |
| 🟢 P2 | 全局仪表盘 | 体验升级的核心 |
| ⚪ P3 | 语音、移动端、GPU 调度 | v3 重点 |

---

## 🔗 相关文档

- [TODO_ZH.md](TODO_ZH.md) — 详细能力清单和验收标准
- [HARNESS_ARCHITECTURE_GUIDE_ZH.md](HARNESS_ARCHITECTURE_GUIDE_ZH.md) — Harness 分层设计
- [HARNESS_CLI_MEMORY_ZH.md](HARNESS_CLI_MEMORY_ZH.md) — CLI 与科研记忆
- [AGENT_PROTOCOL_ZH.md](AGENT_PROTOCOL_ZH.md) — Agent 协作协议
- [PRODUCT_BLUEPRINT_ZH.md](PRODUCT_BLUEPRINT_ZH.md) — 产品蓝图

---

> 本文持续更新。功能想法欢迎邮件：[3653448612@qq.com](mailto:3653448612@qq.com)。
> 建议附上：使用场景、输入、期望输出、失败风险和验收方式。
