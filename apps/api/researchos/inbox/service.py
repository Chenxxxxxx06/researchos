"""Research Inbox persistence and analysis dispatch."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from researchos.agents.enums import AgentType
from researchos.agents.models import AgentRun
from researchos.agents.service import AgentRunService
from researchos.common.errors import NotFoundError
from researchos.common.roles import ProjectRole
from researchos.identity.models import User
from researchos.projects.service import ProjectService

from .models import ResearchInboxItem
from .schemas import CreateInboxItemRequest, InboxAnalysisMode


class ResearchInboxService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.projects = ProjectService(db)

    async def list_items(
        self, actor: User, project_id: uuid.UUID
    ) -> list[ResearchInboxItem]:
        await self.projects.ensure_access(actor, project_id, ProjectRole.VIEWER)
        result = await self.db.execute(
            select(ResearchInboxItem)
            .where(ResearchInboxItem.project_id == project_id)
            .order_by(ResearchInboxItem.created_at.desc())
            .limit(100)
        )
        return list(result.scalars().all())

    async def create_item(
        self,
        actor: User,
        project_id: uuid.UUID,
        payload: CreateInboxItemRequest,
    ) -> ResearchInboxItem:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        item = ResearchInboxItem(
            project_id=project_id,
            source_type=payload.source_type,
            sender=payload.sender.strip() if payload.sender else None,
            title=payload.title.strip(),
            content_text=payload.content_text.strip(),
            original_filename=payload.original_filename,
            media_type=payload.media_type,
            created_by=actor.id,
        )
        self.db.add(item)
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def analyze(
        self,
        actor: User,
        project_id: uuid.UUID,
        item_id: uuid.UUID,
        mode: InboxAnalysisMode,
    ) -> AgentRun:
        await self.projects.ensure_access(actor, project_id, ProjectRole.RESEARCHER)
        item = await self.db.scalar(
            select(ResearchInboxItem).where(
                ResearchInboxItem.id == item_id,
                ResearchInboxItem.project_id == project_id,
            )
        )
        if item is None:
            raise NotFoundError("Research inbox item not found.")

        mode_instructions = {
            "direction": """输出：
1. 一句话核心方向；
2. 明确要求与隐含约束（分开写）；
3. 待确认的问题；
4. 可执行待办，按调研、代码、实验、论文分类；
5. 文献检索关键词与可能需要验证的论文线索（不得虚构引用）；
6. baseline、benchmark、消融和数据风险建议；
7. 建议转成 ResearchOS 中的 Idea、Paper、Experiment 或论文任务。""",
            "meeting_summary": """把内容整理成可追踪的会议纪要：
1. 会议主题与一句话结论；
2. 逐条决定（Decision）及其依据；
3. Action Items：负责人未知时写 TBD，包含优先级、依赖和建议截止时间；
4. 未解决问题与分歧；
5. 提到的数据集、论文、代码、实验和指标；
6. 下次会议前必须准备的材料；
7. 不确定或转写可能错误的位置。不要替与会者补造承诺。""",
            "audio_to_paper": """把这份录音转写稿转换为“论文蓝图 + 可编辑初稿”，但不要虚构
引用、实验结果或统计数字：
1. 可能的题目与一句话主张；
2. Research Question、问题背景、研究缺口和可证伪假设；
3. 方法、数据、baseline、benchmark、消融与评价指标清单；
4. 论文结构（Abstract/Introduction/Related Work/Method/Experiments/Discussion）；
5. 仅根据转写内容起草各节要点；缺证据处标 [NEEDS EVIDENCE]，缺实验处标 [TBD EXPERIMENT]；
6. 从口语中识别应删除的重复、题外话和不确定表述；
7. 给出下一步调研、实现和实验任务，等待用户确认后才能进入正式写作。""",
        }[mode]

        excerpt = item.content_text[:48_000]
        omitted = len(item.content_text) - len(excerpt)
        truncation_note = (
            f"\n注意：原始文本共 {len(item.content_text)} 字符，本次仅分析前 {len(excerpt)} 字符，"
            f"仍有 {omitted} 字符未进入当前上下文。请把超长材料拆分后再次导入。"
            if omitted > 0
            else ""
        )
        message = f"""你正在整理导师、师兄或合作者发来的科研输入。请只根据下面的原始内容分析，
不要补造论文、结果、引用、实验状态或任何人的承诺。严格区分四类信息：
- [原文事实] 可以从输入中直接定位；
- [合理推断] 由输入推导但尚未确认；
- [行动建议] 你提出的下一步；
- [证据缺口] 需要论文、代码、数据或当事人补充。

标题：{item.title}
发送者：{item.sender or "未注明"}
来源类型：{item.source_type}
处理模式：{mode}

原始内容：
{excerpt}
{truncation_note}

{mode_instructions}
"""
        run = await AgentRunService(self.db).create_run(
            actor,
            project_id,
            agent_type=AgentType.RESEARCH,
            message=message,
        )
        item.agent_run_id = run.id
        await self.db.commit()
        return run
