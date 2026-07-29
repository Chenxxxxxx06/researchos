'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { FileSearch2, Loader2, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { createAgentRun, getAgentRun } from '@/lib/api/agents';

const VENUES = ['General CS', 'NeurIPS', 'ICML', 'ACL', 'CVPR', 'Nature'];

export function ReviewerWorkspace({ projectId }: { projectId: string }) {
  const [venue, setVenue] = useState('General CS');
  const [manuscript, setManuscript] = useState('');
  const [runId, setRunId] = useState<string | null>(null);
  const start = useMutation({
    mutationFn: () =>
      createAgentRun(projectId, {
        agent_type: 'research',
        message: reviewerPrompt(venue, manuscript),
      }),
    onSuccess: (result) => setRunId(result.agent_run_id),
  });
  const run = useQuery({
    queryKey: ['reviewer-run', projectId, runId],
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
          <ShieldCheck className="h-5 w-5" /> Reviewer Arena
        </h1>
        <p className="mt-1 text-sm text-muted">
          在投稿前按目标 venue 做一次可追溯的模拟审稿；它是修改清单，不替代正式评审。
        </p>
      </header>
      <div className="grid gap-6 p-6 xl:grid-cols-[24rem_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>创建模拟审稿</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <label className="block text-sm font-medium text-text">
              目标会议 / 期刊
              <select
                value={venue}
                onChange={(event) => setVenue(event.target.value)}
                className="mt-1 h-10 w-full rounded-md border border-border-strong bg-surface px-3"
              >
                {VENUES.map((item) => (
                  <option key={item}>{item}</option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-text">
              稿件文本或结构化摘要
              <textarea
                value={manuscript}
                onChange={(event) => setManuscript(event.target.value)}
                className="mt-1 min-h-80 w-full resize-y rounded-md border border-border-strong bg-surface p-3 text-sm"
                placeholder="粘贴 abstract、method、experiments、limitations；后续会直接连接论文工作区版本。"
              />
            </label>
            <Button
              className="w-full"
              onClick={() => start.mutate()}
              loading={start.isPending}
              disabled={manuscript.trim().length < 80}
            >
              <FileSearch2 className="h-4 w-4" /> 开始评审
            </Button>
            <p className="text-xs leading-5 text-muted">
              评审维度：desk reject、创新性、技术正确性、实验充分性、写作与图表、可复现性、伦理与局限、评分及置信度。
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
            <CardTitle>评审报告</CardTitle>
          </CardHeader>
          <CardContent>
            {!runId && (
              <div className="py-24 text-center text-sm text-muted">
                报告会保留证据缺口、不可验证项和优先级，不把模型意见伪装成真实审稿结论。
              </div>
            )}
            {run.data && ['queued', 'running'].includes(run.data.status) && (
              <div className="flex items-center gap-2 rounded-md bg-info-bg p-4 text-sm text-info">
                <Loader2 className="h-4 w-4 animate-spin" /> Reviewer Agent 正在检查稿件…
              </div>
            )}
            {run.data?.status === 'failed' && (
              <div className="rounded-md bg-danger-bg p-4 text-sm text-danger">
                {run.data.error_json?.message || '评审失败，请先在设置中测试 LLM 连接。'}
              </div>
            )}
            {run.data?.status === 'completed' && (
              <article className="whitespace-pre-wrap text-sm leading-7 text-text">
                {typeof output === 'string' ? output : '运行完成，但没有返回文本报告。'}
              </article>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function reviewerPrompt(venue: string, manuscript: string): string {
  return `You are a rigorous simulated reviewer for ${venue}. Review ONLY the manuscript below.
Do not fabricate citations, facts, scores from other reviewers, or experimental results. Mark anything
that cannot be verified as [UNVERIFIED]. Separate fatal issues from improvements. Return:
1) desk-reject and scope checks; 2) concise summary; 3) strengths; 4) weaknesses with quoted or
section-level evidence; 5) novelty, soundness, significance, clarity, reproducibility, ethics/limitations;
6) missing baselines, benchmarks, ablations and statistical checks; 7) questions for authors;
8) prioritized revision plan; 9) simulated score and confidence with reasons.

MANUSCRIPT:
${manuscript.slice(0, 8000)}`;
}
