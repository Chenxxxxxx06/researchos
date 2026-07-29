'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { FileCode2, FileText, Image, Loader2, Megaphone, PackageCheck } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { createAgentRun, getAgentRun, type AgentType } from '@/lib/api/agents';

type ReleaseKind = 'website' | 'readme' | 'poster';

const RELEASES: Array<{
  kind: ReleaseKind;
  title: string;
  description: string;
  icon: typeof FileCode2;
  agentType: AgentType;
}> = [
  {
    kind: 'website',
    title: '项目宣传页',
    description: '生成 title、authors、links、teaser、method、results、BibTeX 的静态站点变更提案。',
    icon: FileCode2,
    agentType: 'coding',
  },
  {
    kind: 'readme',
    title: 'GitHub README',
    description: '从同一份 Research Story Pack 生成清晰、可复现、不过度宣传的仓库首页。',
    icon: FileText,
    agentType: 'coding',
  },
  {
    kind: 'poster',
    title: '学术 Poster',
    description: '优先复用论文图表与结果卡片，输出低成本 LaTeX poster 内容和版式建议。',
    icon: Image,
    agentType: 'latex',
  },
];

export function ResearchReleaseWorkspace({ projectId }: { projectId: string }) {
  const [kind, setKind] = useState<ReleaseKind>('website');
  const [storyPack, setStoryPack] = useState('');
  const [runId, setRunId] = useState<string | null>(null);
  const selected = RELEASES.find((item) => item.kind === kind)!;
  const start = useMutation({
    mutationFn: () =>
      createAgentRun(projectId, {
        agent_type: selected.agentType,
        message: releasePrompt(kind, storyPack),
      }),
    onSuccess: (result) => setRunId(result.agent_run_id),
  });
  const run = useQuery({
    queryKey: ['release-run', projectId, runId],
    queryFn: () => getAgentRun(projectId, runId!),
    enabled: Boolean(runId),
    refetchInterval: (query) =>
      ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1500 : false,
  });
  const output = run.data?.output_json?.message;

  return (
    <div className="-m-6 min-h-[calc(100vh-3.5rem)] bg-bg">
      <header className="border-b border-border bg-surface px-6 py-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-text">
          <Megaphone className="h-5 w-5" /> Research Release Studio
        </h1>
        <p className="mt-1 text-sm text-muted">
          网站、README 与 Poster 共享一份事实来源；先生成可审查提案，再由人确认发布。
        </p>
      </header>

      <div className="space-y-5 p-6">
        <div className="grid gap-3 md:grid-cols-3">
          {RELEASES.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.kind}
                onClick={() => setKind(item.kind)}
                className={`rounded-xl border p-4 text-left transition-colors ${
                  kind === item.kind
                    ? 'border-accent bg-accent/5'
                    : 'border-border bg-surface hover:bg-surface-2'
                }`}
              >
                <div className="flex items-center gap-2 text-sm font-semibold text-text">
                  <Icon className="h-4 w-4 text-accent" /> {item.title}
                </div>
                <p className="mt-2 text-xs leading-5 text-muted">{item.description}</p>
              </button>
            );
          })}
        </div>

        <div className="grid gap-6 xl:grid-cols-[26rem_minmax(0,1fr)]">
          <Card className="h-fit">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <PackageCheck className="h-4 w-4" /> Research Story Pack
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <textarea
                value={storyPack}
                onChange={(event) => setStoryPack(event.target.value)}
                className="min-h-[28rem] w-full resize-y rounded-md border border-border-strong bg-surface p-3 text-sm"
                placeholder={`项目名与一句话 Hook：
作者、单位：
Paper / Code / Model / Demo 链接：
问题与研究缺口：
三条贡献：
方法摘要：
已核验结果卡片（指标、数据集、run/commit）：
可复用图表路径：
局限：
BibTeX：`}
              />
              <Button
                className="w-full"
                onClick={() => start.mutate()}
                loading={start.isPending}
                disabled={storyPack.trim().length < 80}
              >
                生成 {selected.title} 提案
              </Button>
              <p className="text-xs leading-5 text-muted">
                数字、引用和链接必须来自 Story Pack；缺失信息会标为 TODO。Coding Agent 只能形成补丁提案，
                不会绕过代码审查直接覆盖仓库。
              </p>
              {start.error && (
                <p className="rounded-md bg-danger-bg p-2 text-xs text-danger">
                  {start.error instanceof Error ? start.error.message : '启动失败'}
                </p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>{selected.title} 输出</CardTitle>
            </CardHeader>
            <CardContent>
              {!runId && (
                <div className="py-24 text-center text-sm text-muted">
                  一次维护 Story Pack，后续三个交付物只做版式转换，减少重复工作与事实漂移。
                </div>
              )}
              {run.data && ['queued', 'running'].includes(run.data.status) && (
                <div className="flex items-center gap-2 rounded-md bg-info-bg p-4 text-sm text-info">
                  <Loader2 className="h-4 w-4 animate-spin" /> Release Agent 正在生成提案…
                </div>
              )}
              {run.data?.status === 'failed' && (
                <div className="rounded-md bg-danger-bg p-4 text-sm text-danger">
                  {run.data.error_json?.message || '生成失败，请检查 LLM 与 Agent Worker。'}
                </div>
              )}
              {run.data?.status === 'completed' && (
                <article className="whitespace-pre-wrap text-sm leading-7 text-text">
                  {typeof output === 'string'
                    ? output
                    : run.data.output_json?.patch_id
                      ? `已形成补丁提案 ${run.data.output_json.patch_id}，请前往 AI IDE 审查。`
                      : '运行完成，但没有返回可显示内容。'}
                </article>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function releasePrompt(kind: ReleaseKind, storyPack: string): string {
  const artifact =
    kind === 'website'
      ? 'a minimal responsive static academic project page'
      : kind === 'readme'
        ? 'a polished GitHub README'
        : 'a concise LaTeX academic poster draft and layout specification';
  return `Create ${artifact} using ONLY the Research Story Pack below.
Reuse the same factual hierarchy: title/authors/links, hook, contributions, method, verified results,
figures, limitations, BibTeX. Never invent metrics, citations, awards, links, demos, or qualitative claims.
Write TODO where evidence or an asset is absent. Prefer accessible HTML/Markdown/LaTeX, reproducibility
instructions, descriptive alt text, and a small dependency footprint. For code changes, return a reviewable
patch proposal and do not overwrite unrelated files.

RESEARCH STORY PACK:
${storyPack.slice(0, 8000)}`;
}
