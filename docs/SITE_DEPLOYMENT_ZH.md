# ResearchOS 本地网站快速部署与审核

## 1. 当前部署方式

为了让展示启动足够快，同时保留 PostgreSQL/pgvector、Redis 和对象存储的真实链路，本项目在 Windows 上采用轻量混合模式：

| 层 | 运行方式 | 端口 | 用途 |
|---|---|---:|---|
| PostgreSQL + pgvector | Docker 缓存镜像 `pgvector/pgvector:pg16` | `15432` | 业务数据、全文检索、向量索引 |
| Redis | Docker 缓存镜像 `redis:7-alpine` | `56379` | Agent 队列与运行状态 |
| MinIO | Docker 缓存镜像 `minio/minio` | `9000/9001` | 对象存储与就绪探针 |
| FastAPI | G 盘项目虚拟环境 | `8000` | API、认证、业务与 Agent 调度 |
| Celery Worker | G 盘项目虚拟环境，Windows `solo` pool | — | SQL、引用、阅读卡、综述、实验方案等后台 Agent |
| Next.js | G 盘依赖目录 | `3000` | 审核网页 |

这条路径只拉起已有基础镜像，不执行耗时的 API/Web 镜像重建。完整 Docker Compose 构建仍保留为 `pnpm stack:full`。

本机已验证的非 C 盘 Docker 位置：

- Docker Desktop：`G:\Docker\DockerDesktop`
- Docker WSL 数据盘：`G:\Docker\wsl\disk\docker_data.vhdx`

启动器会优先寻找上述位置；若其他电脑使用 Docker 默认位置，也会自动回退寻找。

## 2. 一条命令启动

在仓库根目录 `G:\code\code_vscode\aireasearch` 执行：

```powershell
pnpm site:up
```

启动器会依次：

1. 检查并按需启动 Docker Desktop；
2. 拉起 PostgreSQL/pgvector、Redis、MinIO，不构建应用镜像；
3. 执行 Alembic `head` 迁移；
4. 幂等补齐 Demo 用户、项目、论文、Mission、阅读卡、综述、实验方案、数据集和 LLM 模板；
5. 启动 API、Celery Worker 和 Web；
6. 等待 `/healthz`、`/readyz` 和登录页真正可访问。

访问入口：

- 网站：[http://localhost:3000/login](http://localhost:3000/login)
- API 文档：[http://localhost:8000/docs](http://localhost:8000/docs)
- MinIO 控制台：[http://localhost:9001](http://localhost:9001)

Demo 账号：

| 字段 | 值 |
|---|---|
| 邮箱 | `demo@researchos.dev` |
| 密码 | `demo-password-123` |

## 3. 审核命令

```powershell
# 服务进程、HTTP 和容器健康状态
pnpm site:status

# 登录并验证 16 条核心 API 链路
pnpm site:verify

# 查看 API、Worker 和 Web 最近日志
pnpm site:logs
```

教师要求主链的浏览器自动验收：

```powershell
pnpm --filter web test:e2e
```

截图输出到 `artifacts/screenshots`，Playwright 报告输出到 `artifacts/playwright-report`。

## 4. 停止与恢复

```powershell
pnpm site:down
pnpm site:up
```

`site:down` 只终止启动器记录的 ResearchOS 进程树，并停止这三个基础设施容器；不会关闭 Docker Desktop，不会删除 Docker volume，也不会扫描或终止其他 Node/Python 进程。重新启动后迁移和 seed 都是幂等的，已有审核数据会保留。

运行时 PID 与日志放在 `artifacts/site-runtime`，该目录已被 Git 忽略。

## 5. 直接审核老师要求的页面

- Demo 项目：`044950a4-5b79-4ac4-b34f-faece338dbc7`
- Demo Mission：`bfe4d5ad-5c7a-45ad-bef4-433ef2b49f1c`

- Mission 五阶段：`/projects/{projectId}/missions/{missionId}`
- 结构化综述：`/projects/{projectId}/missions/{missionId}/review`
- 实验方案：`/projects/{projectId}/missions/{missionId}/experiment-plan`
- SQL Data Lab：`/projects/{projectId}/missions/{missionId}/data-query`
- 引用整理：`/projects/{projectId}/missions/{missionId}/citations`
- 课题组后台：`/projects/{projectId}/manage`

以上页面都通过同一登录态、项目权限、真实 API 和同一 PostgreSQL 数据库工作，不是独立静态 Demo。

## 6. 常见问题

### 端口被占用

快速部署刻意避开本机常见的数据库端口，但 Web/API 仍需要 `3000`、`8000`。先运行：

```powershell
pnpm site:status
```

若显示 HTTP 已存在但 PID 未被启动器记录，请先确认占用者，不要直接批量结束 Node/Python 进程。

### 页面可打开但后台 Agent 不结束

检查 Worker：

```powershell
pnpm site:status
pnpm site:logs
```

正常日志会包含 `celery@... ready`。Redis 必须处于 healthy。

### 完全重建应用镜像

仅在需要验证完整容器镜像时执行：

```powershell
pnpm stack:full
```

这会构建 API、Worker 和 Web 镜像，明显慢于本地审核路径。
