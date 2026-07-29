'use client';

import { useQuery } from '@tanstack/react-query';
import {
  Bot,
  Braces,
  CheckCircle2,
  ChevronRight,
  GitBranch,
  Network,
  PauseCircle,
  ShieldCheck,
  UserRound,
} from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { listAgentRuns } from '@/lib/api/agents';
import { listProjectMembers } from '@/lib/api/projects';

const AGENT_ROLES = [
  ['Evidence Agent', '检索、Zotero、引用与证据图谱'],
  ['Idea Agent', '问题—缺口—假设与最小可验证创新'],
  ['Coding Agent', '代码理解、补丁、测试与 Git 交付'],
  ['Experiment Planner', 'baseline、benchmark、消融和预算'],
  ['Experiment Runner', 'DAG 调度、真实终端、日志与指标'],
  ['Repro Agent', '环境锁定、重跑与结果 diff'],
  ['Writer Agent', '基于已验证证据和结果撰写 LaTeX'],
  ['Figure Agent', '图、表、公式、项目页和 poster'],
  ['Reviewer Agent', 'venue rubric、评分、修改优先级'],
  ['Release Agent', 'README、项目主页、匿名与投稿包检查'],
] as const;

export function AgentOrchestrationWorkspace({ projectId }: { projectId: string }) {
  const members = useQuery({
    queryKey: ['project-members', projectId],
    queryFn: () => listProjectMembers(projectId),
  });
  const runs = useQuery({
    queryKey: ['agent-runs', projectId, 'orchestration'],
    queryFn: () => listAgentRuns(projectId, { limit: 100 }),
    refetchInterval: 5000,
  });

  return (
    <div className="-m-6 min-h-[calc(100vh-3.5rem)] bg-bg">
      <header className="border-b border-border bg-surface px-6 py-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-text">
          <Network className="h-5 w-5" /> 协作树与 Agent 控制台
        </h1>
        <p className="mt-1 text-sm text-muted">
          人员、Agent run 与产物按项目树归属；任务执行使用 DAG，二者不要混为一棵树。
        </p>
      </header>

      <div className="grid gap-5 p-6 xl:grid-cols-[minmax(20rem,0.9fr)_minmax(28rem,1.2fr)]">
        <Card>
          <CardHeader>
            <CardTitle>真实协作树</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <TreeRow icon={GitBranch} label="Project workspace" meta="共享根与 Git 主线" depth={0} />
            <TreeRow icon={UserRound} label="Human team" meta={`${members.data?.length ?? 0} 人`} depth={1} />
            {members.data?.map((member) => {
              const ownedRuns = runs.data?.items.filter((run) => run.user_id === member.user_id) ?? [];
              return (
                <div key={member.user_id}>
                  <TreeRow
                    icon={UserRound}
                    label={member.display_name}
                    meta={`${member.role} · ${ownedRuns.length} runs`}
                    depth={2}
                  />
                  {ownedRuns.slice(0, 4).map((run) => (
                    <TreeRow
                      key={run.id}
                      icon={Bot}
                      label={`${run.agent_type} / ${run.id.slice(0, 8)}`}
                      meta={run.status}
                      depth={3}
                    />
                  ))}
                </div>
              );
            })}
            <TreeRow icon={Braces} label="Shared artifacts" meta="论文、实验、图表、审稿报告" depth={1} />
            <p className="rounded-md bg-info-bg p-3 text-xs leading-5 text-info">
              当前实体已经保留 user_id / created_by / imported_by。下一步会在所有产物上统一加入
              visibility 与 branch/worktree_id，形成 private、team、published 三层可见性。
            </p>
          </CardContent>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader>
              <CardTitle>统一协调器与角色边界</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 sm:grid-cols-2">
              {AGENT_ROLES.map(([name, responsibility]) => (
                <div key={name} className="rounded-lg border border-border bg-surface-2 p-3">
                  <div className="flex items-center gap-2 text-sm font-medium text-text">
                    <Bot className="h-4 w-4 text-accent" /> {name}
                  </div>
                  <p className="mt-1 text-xs leading-5 text-muted">{responsibility}</p>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>不停轴运行规则</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:grid-cols-3">
              <Rule
                icon={CheckCircle2}
                title="可以自动继续"
                text="低风险检索、解析、静态检查、已批准预算内的实验和报告生成。"
              />
              <Rule
                icon={PauseCircle}
                title="必须暂停"
                text="首次 SSH、付费/大规模实验、修改主分支、完整性失败、最优方案和投稿。"
              />
              <Rule
                icon={ShieldCheck}
                title="失败即关闭"
                text="没有证据、没有指标、产物哈希不一致或超预算时，不允许悄悄跳过。"
              />
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function TreeRow({
  icon: Icon,
  label,
  meta,
  depth,
}: {
  icon: typeof GitBranch;
  label: string;
  meta: string;
  depth: number;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md px-2 py-1.5 hover:bg-surface-2" style={{ paddingLeft: 8 + depth * 18 }}>
      {depth > 0 && <ChevronRight className="h-3 w-3 text-faint" />}
      <Icon className="h-4 w-4 text-muted" />
      <span className="min-w-0 flex-1 truncate text-text">{label}</span>
      <span className="text-[11px] text-faint">{meta}</span>
    </div>
  );
}

function Rule({
  icon: Icon,
  title,
  text,
}: {
  icon: typeof CheckCircle2;
  title: string;
  text: string;
}) {
  return (
    <div className="rounded-lg border border-border p-3">
      <div className="flex items-center gap-2 text-sm font-medium text-text">
        <Icon className="h-4 w-4 text-accent" /> {title}
      </div>
      <p className="mt-2 text-xs leading-5 text-muted">{text}</p>
    </div>
  );
}
