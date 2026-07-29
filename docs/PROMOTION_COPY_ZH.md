# ResearchOS 宣传文案包

本文件为 GitHub、项目主页、Poster、演示视频、交流群和合作招募提供统一文案。
对外使用前必须核对当前功能状态，不得把 TODO 写成已完成能力。

## 一句话定位

ResearchOS 是一个面向 AI 科研全流程的垂直 Agent Harness：让论文调研、Idea
形成、代码实现、实验追踪、结果分析、论文写作、模拟审稿和成果发布共享同一套
上下文、工具、证据链与人工审批机制。

## 30 秒介绍

今天的科研工具往往彼此割裂：Zotero 保存论文，IDE 编写代码，服务器运行实验，
表格记录结果，Overleaf 撰写论文，聊天软件保存导师意见。真正困难的不是再增加
一个聊天机器人，而是让这些材料可以被 Agent 安全调用，并且能回答：

> 论文里的这条结论，来自哪篇文献、哪个实验、哪个 commit 和哪份 artifact？

ResearchOS 正在构建这个连接层。它以项目为边界，将模型、工具、科研记忆、
实验 provenance、多 Agent 协作与人工闸门统一起来。

## GitHub 简介

```text
ResearchOS — A provenance-first scientific Agent Harness.
Research → Code → Experiment → Paper → Review → Release.
```

中文版本：

```text
ResearchOS —— 以证据链为核心的科研 Agent Harness。
从调研、代码、实验到论文、审稿与发布，一个可追溯工作台。
```

## 项目主页 Hero

### 标题

Your research loop, finally connected.

### 副标题

ResearchOS 将论文、Idea、代码、实验、图表、稿件和评审连接成可暂停、可恢复、
可审查的科研工作流。模型可以更换，证据链不会丢失。

### 按钮

- Explore the Harness
- Read the Architecture
- View the Roadmap
- GitHub

## 核心卖点

### Provenance-first

每个重要主张最终绑定到 Paper、Evidence、Run、Artifact 与 Commit。模型输出默认
只是候选，不会自动变成论文事实。

### One research context

Zotero 文献、导师消息、代码状态、实验进度、论文模板和 Reviewer 共享同一个
项目上下文，但按照权限、版本和证据状态分层加载。

### Human-governed autonomy

Agent 可以持续执行低风险任务，但研究范围、实验真实性和对外发布必须经过人工
确认。系统遇到证据不足、预算耗尽或重复失败时会停止，而不是无限循环。

### From work to communication

同一份 Research Story Pack 可以生成项目宣传页、GitHub README 和 Poster，
减少重复劳动和对外表述漂移。

## 当前可演示能力

- Zotero 连接、同步和论文推荐入口；
- Research Copilot 与 LLM 连通测试；
- 创新点、研究缺口与下一步实验提取；
- 科研收件箱、会议总结和转写稿转论文蓝图；
- 本地受限真实终端、Git 状态与可审查代码 Patch；
- 实验进度和数据输入链路概览；
- LaTeX 论文工作区与模板；
- 实时会议 DDL、模拟 Reviewer；
- 项目页、README、Poster Release Studio；
- `researchos` / `ros` CLI 粗版；
- 科研记忆与 Context Manifest 粗版。

## 必须诚实说明的边界

- SSH/HPC/Slurm 尚未实现；
- 任意命令、真实 LaTeX 和第三方代码仍需隔离执行器；
- 真实音频 ASR 和说话人分离尚未实现；
- Mission DAG 和自动多 Agent 调度仍是设计与本地 scaffold；
- PDF 标注、多模态解析、引用图谱和可复现重跑仍在 TODO；
- 当前版本是 `0.1.0-alpha.1`，用于架构验证和共同设计，不适合无人监管生产使用。

## 合作招募文案

ResearchOS 仍处于非常早期的 alpha 阶段。我们希望和真正跑实验、写论文、带学生、
维护科研基础设施的人一起讨论：

- 什么才是科研场景真正有用的长期记忆？
- 哪些任务可以自动执行，哪些必须由人确认？
- 如何评价 Idea Agent、Experiment Agent 和 Reviewer Agent？
- 如何让失败实验和负面结果也成为团队资产？
- 如何把一个项目可靠地交接给师弟、师妹或未来的自己？

如果你对 Agent Harness、科研工作流、实验平台、论文写作或科研教育感兴趣，欢迎
联系：`3653448612@qq.com`。

## 演示视频脚本

1. 输入一句研究目标。
2. 展示 Zotero 和文献推荐。
3. 将导师消息放入 Research Inbox，生成方向和 Action Items。
4. Coordinator 给出研究范围、指标、预算与 Agent DAG。
5. Coding Agent 形成可审查 Patch。
6. 实验面板展示进度、数据链路、baseline 和 ablation 计划。
7. 结果通过 evidence gate 后进入论文工作区。
8. Reviewer Arena 输出修改清单。
9. 同一 Story Pack 生成项目页、README 和 Poster。
10. 最后展示 Claim → Evidence → Run → Artifact → Commit。

## 社交媒体短文案

### 版本 A

我正在做 ResearchOS：一个面向 AI 科研的垂直 Agent Harness。它不是把所有内容
塞给一个超级 Agent，而是把论文、代码、实验、论文写作与评审连接成有证据链、
权限和人工闸门的工作流。目前已完成第一版 CLI、Zotero、实验进度、论文工作区、
Reviewer 和成果发布骨架。欢迎交流：3653448612@qq.com

### 版本 B

如果 AI 帮你写出论文中的一个数字，你能否追溯到对应 run、配置、commit 和
artifact？ResearchOS 希望把答案从“可能可以”变成系统默认能力。

### 版本 C

模型会更新，Prompt 会修改，实验会失败，成员会毕业。真正应该留下来的是研究
决策、证据链和可复现过程。这是 ResearchOS 想解决的问题。

## 项目署名

ResearchOS is a proprietary project owned by **Chenxxxxxx06**.
Copyright © 2024–2026 Chenxxxxxx06. All rights reserved.
