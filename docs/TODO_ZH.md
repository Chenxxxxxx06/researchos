# ResearchOS 能力 TODO

本文不按“第几阶段”包装进度，只按真实能力、完成标准和安全边界维护。状态含义：

- `✅ 可用骨架`：主链路已进入代码，可以运行或产生可审查记录，但仍需强化。
- `🟡 正在深化`：已有部分数据/API/UI，尚不能作为完整承诺。
- `⚪ 待实现`：仅完成产品与接口设计，不应在 README 宣称已可用。

## Agent 与多人协作

| 能力 | 状态 | 最小完成标准 |
|---|---|---|
| 项目→成员→Agent Run→Artifact 归属树 | ✅ 可用骨架 | 页面读取真实成员和运行记录；下一步增加 `visibility`、`owner_id`、共享审批 |
| Coordinator + 专项 Agent 协议 | ✅ 可用骨架 | 使用 `researchos.handoff/v1`、租约、心跳、幂等键、人工闸门，见 `AGENT_PROTOCOL_ZH.md` |
| 持久化科研 Mission DAG | ✅ 可用骨架 | 17 节点任务图、依赖、lease/heartbeat、幂等、重试、Artifact、Gate 和 Event 已落地；常驻 Scheduler、自动派发与真实预算扣减仍待补齐 |
| Prompt / Role / Workflow Registry | ⚪ 待实现 | 版本化、评测集、回滚、变更日志、每次运行记录版本 |
| Agent 评测与自动回归 | ⚪ 待实现 | 任务指标 + LLM judge + 人工抽检，低于阈值禁止晋级 |
| 多人实时共同编辑 | ⚪ 待实现 | 论文用 CRDT；代码用 worktree/branch；实验配置用显式锁与审批 |
| CLI / 终端封装 | ✅ 可用骨架 | `init/login/doctor/projects/ask/chat/runs/context/memory/mission/adapters/release` |
| Durable Mission CLI | 🟡 正在深化 | 当前为本地 receipt + 单 Coordinator Run；待数据库 DAG、resume、lease、heartbeat |
| Agent Dispatch Reconciler | ⚪ 待实现 | 扫描 `dispatch_pending`/超时 queued run，以幂等键重派并告警 |
| Skill Registry 与 Skill 评测 | ⚪ 待实现 | `SKILL.md` + manifest + scripts/references/assets；版本、权限、依赖、样例任务、确定性测试和回滚齐全 |
| 分层 System Prompt Registry | ⚪ 待实现 | Harness Policy / Role / Skill / Task / Context 分层版本化；运行记录保存各层 hash，禁止把动态资料塞进稳定策略 |
| 科研上下文压缩与恢复 | ⚪ 待实现 | 压缩为 Goal/Decision/Evidence/Run/Artifact/Open Question，不把未验证推断提升为事实，压缩前后可追溯 |
| 社区 Skill / Prompt / Workflow Registry | ⚪ 待实现 | 签名 manifest、许可证、权限声明、评测报告、信任等级、撤回机制；社区包默认不可执行任意命令 |

## 文献与知识

| 能力 | 状态 | 最小完成标准 |
|---|---|---|
| Zotero 连接、检测、同步和推荐入口 | ✅ 可用骨架 | 项目级连接，Key 不回传；下一步加密保存与增量定时同步 |
| 独立参考文献中心 | ✅ 可用骨架 | Zotero 配置、同步、论文库与 Research Copilot 跳转 |
| PDF 标注与行内高亮 | ⚪ 待实现 | 坐标锚点、原文引用、评论线程、PDF 版本迁移 |
| 论文自动标签与智能分类 | ⚪ 待实现 | 规则 + 模型双通道、置信度、人工修正、增量重算 |
| 自动文献图谱与引用网络 | ⚪ 待实现 | Paper/Claim/Method/Dataset 边，来源可追溯，支持时间与主题过滤 |
| 多模态论文解析 | ⚪ 待实现 | 图片、图表、表格、公式定位和跨模态引用，不丢页码/图号 |

## 代码与运行时

| 能力 | 状态 | 最小完成标准 |
|---|---|---|
| 本地真实终端 | ✅ 可用骨架 | 仅 local 环境；argv 执行、固定命令白名单、项目目录边界、超时与输出上限 |
| Git 状态与历史读取 | ✅ 可用骨架 | 只读命令真实执行；写操作仍通过可审查 Patch |
| 任意命令沙箱 | ⚪ 待实现 | 容器/gVisor/微虚机隔离、资源配额、网络与秘密权限、审计日志 |
| SSH / HPC / Slurm | ⚪ 待实现 | 主机指纹校验、秘密托管、PTY、断线恢复、端口与命令策略、任务取消 |
| Claude / Codex 风格 CLI | ✅ 可用骨架 | 本地项目初始化、真实 API Agent Turn、会话、上下文、记忆与运行状态 |
| 外部 Harness adapters | ⚪ 待实现 | Claude/Codex/OpenClaw/nanobot 当前只发现安装和跳转，不迁移其代码 |
| 断线后持续执行 Control Plane | ⚪ 待实现 | 提交后由服务端队列接管；JobSpec 持久化、lease/heartbeat、日志游标、checkpoint、幂等重试、取消与重连，不依赖浏览器或 SSH 会话存活 |
| Mission / 实验运行隔离 | ⚪ 待实现 | 每个 Mission 使用容器/工作树/namespace；CPU/GPU/内存/磁盘/网络/秘密配额可审计，失败后可回收 |
| Server Lab 资源观测页 | ⚪ 待实现 | NVML 为稳定采集接口，`nvidia-smi` 为人工诊断后备；展示 GPU 显存/利用率/温度/进程、CPU/内存/磁盘、队列与心跳 |

## 实验与可复现性

| 能力 | 状态 | 最小完成标准 |
|---|---|---|
| Run 进度与数据输入流可视化 | ✅ 可用骨架 | 真实进度字段、阶段、ETA、数据流节点和异常提示 |
| 自动化实验 DAG | ⚪ 待实现 | immutable DAG、缓存、重试、依赖、资源声明、节点级 provenance |
| Baseline / Benchmark / Ablation Planner | 🟡 正在深化 | 从论文证据和项目任务生成候选，不虚构可用代码或结果 |
| 统一训练遥测协议 | ⚪ 待实现 | 指标、日志、artifact、heartbeat、dataset/model/commit/environment digest |
| 可复现性检查 | ⚪ 待实现 | 固定环境重跑、容差策略、指标/文件/图表 diff、失败归因 |
| 数据链路预览 | ⚪ 待实现 | schema、样例、分布、增强前后、泄漏与异常值检查 |
| GPU 感知实验调度器 | ⚪ 待实现 | 先按显存/设备/依赖筛选，再以优先级+aging+deadline 排序，best-fit 装箱和 backfill；支持 Slurm Job Array、并发上限与 checkpoint-aware 抢占 |
| GPU 空转与异常诊断 | ⚪ 待实现 | 对低利用率、OOM、NaN、僵死进程、无 heartbeat、数据加载瓶颈告警；输出可解释原因和安全处置建议 |
| 服务器并行实验助手 | ⚪ 待实现 | 根据资源快照和实验矩阵生成 dry-run 排程，解释为何不能并行、推荐 batch/worker/array 参数，指标以“可验证有效实验 / GPU-hour”为核心 |

## 论文、审稿与成果发布

| 能力 | 状态 | 最小完成标准 |
|---|---|---|
| LaTeX 工作区与模板区域 | ✅ 可用骨架 | 模板入口、文件编辑、AI 建议；真实 PDF 编译仍需隔离 worker |
| 按 venue 自动排版 | ⚪ 待实现 | 官方模板版本锁定、格式检查、匿名规则、页数与补充材料检查 |
| Reviewer Arena | ✅ 可用骨架 | venue 选择、模拟审稿、证据缺口标记、评分理由；当前结果为自由文本，待绑定论文版本和结构化 rubric |
| Reviewer 复审闭环 | ⚪ 待实现 | 论文版本→venue rubric→引用/代码/正确性检查→结构化评分→修改计划→新旧版本 diff→复审；保留每条意见证据 |
| 会议 DDL | ✅ 可用骨架 | 实时读取 CCFDDL 中文 iCal，显示来源并支持订阅；抓取失败可降级，投稿前仍需核对会议官网 |
| Venue-aware Idea Gate | ⚪ 待实现 | 按 venue 调整创新、证据、baseline、消融、复现和算力/时间门槛；不把等级直接等同于“自动生成更激进 idea” |
| Research Story Pack | ✅ 可用骨架 | 网站/README/Poster 共用事实包，缺信息标 TODO，不复制未核验数字 |
| 项目宣传页面 Agent | ✅ 可用骨架 | 生成可审查代码提案；下一步加截图回归、可访问性与自动部署审批 |
| GitHub README Agent | ✅ 可用骨架 | 从 Story Pack 生成补丁；保留安装、复现、引用和许可证 |
| Poster Agent | ✅ 可用骨架 | 复用论文图表与结果卡；下一步接入 PDF/PPTX 导出和印刷检查 |
| GitHub Pages 宣传页 | ✅ 已部署 | `docs/site` 零运行时依赖；当前由 `gh-pages` 发布，合并默认分支后统一切换到 Pages Workflow 并补可访问性回归 |
| GitHub Tag Release | ✅ 可用骨架 | Tag 必须匹配 VERSION，后端/前端全绿后才生成包、校验和与 prerelease |

## 科研收件箱

| 能力 | 状态 | 最小完成标准 |
|---|---|---|
| 消息/文本/转写稿方向提取 | ✅ 可用骨架 | 原文与 AI 总结分离，输出目标、约束、证据缺口和待办 |
| 会议总结 | ✅ 可用骨架 | 决定、负责人、依赖、分歧、Action Items 和不确定转写 |
| 语音转论文 | 🟡 正在深化 | 已支持转写稿→论文蓝图；待接对象存储、ASR、说话人分离与时间戳 |

## 仍需优先补齐的工程质量

- API Key 与 SSH 密钥使用 KMS/系统密钥环加密，日志永久脱敏。
- 真实实验、LaTeX、任意 shell 和第三方代码必须进入隔离运行时。
- 长任务必须由持久化 Control Plane 托管；`tmux`/`screen` 只作为人工应急工具，不能代替任务状态、重试和审计。
- 每一条论文结论绑定 Claim → Evidence → Run → Artifact → Commit。
- 为新增页面补可访问性、E2E、失败/空状态和中英文文案。
- 删除 README 中随时间失真的测试数量与“已生产可用”宣传。
- 增加备份恢复、迁移回滚、审计导出、速率限制与成本预算。

完整 Harness、Skill、System Prompt、上下文压缩、持续执行和 GPU 调度方向见
[ResearchOS Harness 架构实施指南](HARNESS_ARCHITECTURE_GUIDE_ZH.md)。

## 功能等你来提供想法！

如果你有科研流程、Agent 角色、实验管理、写作或成果传播方面的需求，欢迎联系：
`3653448612@qq.com`。建议同时说明使用场景、输入、期望输出、失败风险和验收方式。
