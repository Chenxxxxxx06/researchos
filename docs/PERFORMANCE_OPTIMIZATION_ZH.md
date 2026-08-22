# ResearchOS 性能优化说明

## 根因与结果

实机日志确认，主要卡顿不是按钮动画，而是 Windows 本地启动器使用 `next dev`：首次进入一个路由时会现场编译 1,000–2,500 个模块，单次等待约 3–16 秒；同时 API 被错误地按 Worker 配置为 `DB_USE_NULLPOOL=true`，每个请求都重新建立 PostgreSQL 连接。

现在 `pnpm site:up` 默认使用带增量失效判断的 `next build` + `next start`，源代码和 API 地址未变化时直接复用构建；API 使用预热连接池，只有 Celery Worker 保留 NullPool。在加入 26 节点 Mission Control、能力账本和证据排序面板后，实测核心路由 click → route active 的首轮 p95 为 **252.21ms**，缓存轮 p95 为 **237.42ms**，认证 GET API p95 为 **71.70ms**，仍低于既定 800ms/300ms 门槛。原始报告写入 `artifacts/performance/latest.json`。

## 已落地的优化

### 1. 点击立即反馈

- 左侧导航点击后立即把图标切换为 loading 状态，而不是等新页面完成请求后才反馈。
- 当前页重复点击也会产生短暂按压/加载反馈，避免被误认为按钮失效。
- Release 类型卡增加 `aria-pressed`、按下状态和明确的 active 样式。
- 成果生成先创建 durable job / AgentRun，再后台执行；用户不需要等待整个模型任务结束才收到响应。

### 2. 路由与启动模式

- `scripts/site.ps1` 默认启动 production server，彻底消除点击后的即时编译。
- 构建依据前端源码、共享 schema、锁文件和 API 地址自动失效；无变化时不重复构建。
- 可见的主导航保留 Next.js production prefetch；隐藏在 More 菜单里的路由在 1.5 秒后预热。
- development 模式不再一次性预取全部路由，避免多个编译器争抢 CPU、磁盘和主线程。
- 确实需要 HMR 时可先设置 `$env:RESEARCHOS_WEB_MODE='dev'`，启动器会改用 Turbopack。

### 3. 请求与缓存

- 全局查询 stale window 提升到 60 秒、内存保留 15 分钟；窗口聚焦不重复请求，回到刚访问过的页面先从内存同步绘制。
- 数据变更仍由 mutation 精确 invalidate；失效数据会在 mount/reconnect 后台刷新，运行中任务继续使用自己的短轮询或 WebSocket。
- API 进程使用 10 个常驻 PostgreSQL 连接并在启动时预热；Worker 因跨 event loop 安全要求单独使用 NullPool。
- Release Studio 的项目、论文、Idea、实验和 LaTeX 项目查询设置 30 秒 stale window。
- AutoDesign service health 缓存 10 秒，生成历史缓存 5 秒。
- 运行中的任务按 1.2 秒轮询；终态后停止轮询并刷新历史。
- LaTeX 使用 source fingerprint。完全相同的文件快照直接复用已生成 PDF，不重复调用 TeX。
- PDF URL 以 job id 标识且响应使用 private immutable cache。

### 4. LaTeX 防抖

- 编辑停止 900ms 后才保存并编译，不对每个键盘事件发请求。
- 新编辑发生在保存请求期间时，旧版本不会触发无意义的 PDF 编译；下一次稳定快照会继续保存。
- 首次打开论文时自动编译一次；相同内容命中 PDF cache。
- `latexmk` 在后台线程运行，不阻塞 FastAPI event loop。
- 编译设置 30 秒上限，日志设置 200,000 字符上限，shell escape 关闭。

### 5. RAG 减少上下文浪费

- 向量与关键词各召回 40 条后做 RRF，不把全部论文正文塞进模型。
- 每篇优先最多 3 个 chunk，降低单篇论文淹没上下文的概率。
- Research Agent 先搜索本地 corpus，再调用外部论文搜索，避免重复网络请求。
- 用户明确选择 section 时走精确读取，不再进行一次相似度搜索。

### 6. 架构隔离

AutoDesign 保持独立服务。核心 API 不安装 AutoDesign 的 Playwright、Pillow、视频和视觉评估依赖；成果发布通过短 HTTP 创建请求与状态代理连接。这样不会显著增加 ResearchOS API 的启动时间和常驻内存。

### 7. 前端负载

- `lucide-react` 与 `recharts` 使用 package import optimization。
- Recharts/运行详情从实验首页主 chunk 中拆出，只有选择具体运行时才加载，并立即显示 skeleton。
- production build 的共享首屏 JS 为 103kB；核心项目页 First Load JS 为 132–174kB。

## 建议监控的指标

不能只凭“感觉快”判断优化。建议在生产环境记录：

| 指标 | 建议目标 | 采集位置 |
|---|---:|---|
| 导航 click → loading indicator | < 50ms | Web Performance API |
| 导航 click → route interactive | p95 < 800ms | Next.js client instrumentation |
| 普通 GET API | p95 < 300ms | FastAPI middleware |
| AgentRun 创建 | p95 < 500ms | `/agents/runs` |
| AutoDesign ReleaseJob 创建 | p95 < 1s | `/releases`，不含完整生成 |
| LaTeX 小文档冷编译 | p95 < 5s | `duration_ms` |
| LaTeX 缓存命中 | p95 < 200ms | engine 后缀 `-cache` |
| RAG 查询 | p95 < 800ms | `knowledge.rag_search` tool call |
| WebSocket 首 token | p95 < 2.5s + 模型排队 | Agent events |

## 下一轮优先级

1. **Release Story Pack 聚合接口**：当前前端仍需要读取论文、Idea、实验和指标；可改为单个后端 projection，消除实验指标 N+1 请求。
2. **WebSocket 取代轮询**：AgentRun 已有 WebSocket；AutoDesign 可将 SSE 转发为 ResearchOS domain event，运行中不再轮询。
3. **数据库慢查询观测**：启用 `pg_stat_statements`，为 p95 超过 200ms 的 project-scoped 查询增加复合索引。
4. **RAG 两级缓存**：缓存 query embedding 与相同 mission/query 的 RRF 结果；论文索引变化时按版本失效。
5. **编译队列**：多人协作或大文档场景把 TeX 移到专用 Worker，按项目取消旧快照，只保留最新编译。
6. **细粒度请求取消**：让全部 queryFn 消费 TanStack Query 的 AbortSignal，离开页面时取消尚未完成的低优先级 GET。
7. **AutoDesign 运行配额**：按项目设置并发数和成本预算，避免连续点击产生多个昂贵设计任务。

## 验证方式

```bash
pnpm --filter web typecheck
pnpm --filter web build
pnpm --filter web test:performance
cd apps/api
uv run ruff check .
uv run mypy researchos
uv run pytest -q
```

端到端测试 `apps/web/e2e/smoke.spec.ts` 会实际点击 `[data-nav-segment="release"]`，等待 URL 切换，并依次点击 Website、README、Poster、Slides 四个发布类型，防止按钮再次退化为无响应状态。
