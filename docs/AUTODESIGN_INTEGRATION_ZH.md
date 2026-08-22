# AutoDesign 成果发布集成

## 代码位置

AutoDesign 以浅克隆 Git 子模块接入：

```text
integrations/AutoDesign
```

固定来源：`https://github.com/Yaxin9Luo/AutoDesign.git`。首次克隆 ResearchOS 后执行：

```bash
git submodule update --init --depth 1
```

Windows 可直接运行仓库根目录的：

```bat
start-autodesign.cmd
```

脚本会初始化子模块、执行 `uv sync`、首次安装 Chromium renderer，并在 `http://localhost:8010` 启动 AutoDesign。

## ResearchOS 接入边界

ResearchOS 不复制 AutoDesign 的内部 pipeline，也不把它的依赖安装进核心 API。集成采用服务边界：

```text
Release Studio
  → POST /projects/{project_id}/releases
  → ReleaseService
  → AutoDesign POST /api/generate
  → AutoDesign run id
  → ResearchOS 轮询 /api/runs/{id}/status
  → AutoDesign /api/runs/{id}/artifact
  → Release Studio 预览 / 下载
```

ResearchOS 持久化 `release_generation_jobs`，包括类型、固定模型、状态、外部 run id、进度、错误和成果元数据。

## 模型规则

成果发布只接受项目中已启用且模型名精确为 `qwen-plus` 的 OpenAI-compatible 配置。API key 解密后只进入 AutoDesign 启动请求头，不写入任务表、日志或前端。

ResearchOS 为 AutoDesign 的以下文字角色显式传递 `qwen-plus`：

- Designer
- Planner
- Prompt Enhancer
- Claim Graph
- Deck Outline
- Paper Memory
- Critic
- Composer
- Ingest

这满足当前项目的统一模型策略。需要注意：纯文本 `qwen-plus` 不具备完整视觉模型能力，AutoDesign 的确定性 DOM/layout gate 仍可运行，但视觉 Critic 的能力取决于所配置服务是否接受图像输入。如果后续允许单独的 VLM，应在产品设置中显式展示该差异，而不是静默替换模型。

## 输出位置

AutoDesign 的原生成文件保存在：

```text
integrations/AutoDesign/out/runs/<external_run_id>/final/
```

常见成果：

| 类型 | 主要文件 |
|---|---|
| Poster | `poster.html`, `preview.png`, `poster.pdf` |
| Slides | `deck.html`, `deck.pdf`, 可选 `deck.pptx` |
| Website | `index.html`, `preview.png` |

Release Studio 显示预览、质量诊断、外部 run id、本地目录和下载入口。ResearchOS 只保存索引，不复制大型成果文件。

README 不经过 AutoDesign：它使用 ResearchOS Coding Agent + qwen-plus 生成 `README.md` Patch，用户审查后再应用到工作区。

## 配置

API 进程使用：

```env
AUTODESIGN_BASE_URL=http://host.docker.internal:8010
AUTODESIGN_PUBLIC_URL=http://localhost:8010
AUTODESIGN_START_TIMEOUT_SECONDS=30
```

- `BASE_URL`：ResearchOS API 能访问的内部地址。
- `PUBLIC_URL`：浏览器打开预览和下载时使用的地址。

Docker Compose 已配置 `host.docker.internal:host-gateway`；Windows 快速启动器中的 API 直接运行在宿主机，因此 `scripts/site.ps1` 会把两者显式设为 `http://localhost:8010`，避免宿主机反向访问 `host.docker.internal` 时出现空响应。

服务健康与模型就绪是两个独立状态：成果发布页始终检查 AutoDesign 是否可达；即使服务自身没有全局凭证，只要项目稍后配置了 `qwen-plus`，ResearchOS 也会在单次生成请求中安全注入凭证。

## 故障定位

1. Release Studio 显示“缺少 qwen-plus”：检查项目 LLM 配置的 model、active、provider 和 API key。
2. 显示“AutoDesign 未就绪”：运行 `start-autodesign.cmd`，访问 `http://localhost:8010/api/health`。
3. 任务创建后失败：在 UI 查看错误，并检查 AutoDesign 终端和 `out/runs/<id>/run_events.jsonl`。
4. 有成果但无法预览：检查 `AUTODESIGN_PUBLIC_URL` 是否能从浏览器访问。
5. 需要更新 AutoDesign：

```bash
git submodule update --remote integrations/AutoDesign
git add integrations/AutoDesign
git commit
```
