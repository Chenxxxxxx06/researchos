'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, BookOpen, Check, FileClock, FileKey2, History, Quote, RefreshCw, Save, ScrollText, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { listMissionPapers } from '@/lib/api/knowledge';
import { getAgentRun } from '@/lib/api/agents';
import { generateReviewOutline, generateReviewSection, getReview, listReviewVersions, updateReviewSection, type ReviewSection } from '@/lib/api/reviews';
import { useI18n } from '@/lib/i18n';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';

export function ReviewWorkspace({ projectId, missionId }: { projectId: string; missionId: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const queryClient = useQueryClient();
  const review = useQuery({ queryKey: ['mission-review', projectId, missionId], queryFn: () => getReview(projectId, missionId), retry: false });
  const papers = useQuery({ queryKey: ['mission-papers', projectId, missionId], queryFn: () => listMissionPapers(projectId, missionId) });
  const versions = useQuery({ queryKey: ['review-versions', projectId, missionId], queryFn: () => listReviewVersions(projectId, missionId), enabled: Boolean(review.data) });
  const [selectedId, setSelectedId] = useState('');
  const current = useMemo(() => review.data?.sections.find((section) => section.id === selectedId) ?? review.data?.sections[0], [review.data, selectedId]);
  const [title, setTitle] = useState('');
  const [purpose, setPurpose] = useState('');
  const [body, setBody] = useState('');
  const [citations, setCitations] = useState<string[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  useEffect(() => {
    if (current) {
      setSelectedId(current.id);
      setTitle(current.title);
      setPurpose(current.purpose);
      setBody(current.body);
      setCitations(current.citations_json);
    }
  }, [current]);
  const generate = useMutation({
    mutationFn: () => generateReviewOutline(projectId, missionId, Boolean(review.data)),
    onSuccess: (data) => {
      queryClient.setQueryData(['mission-review', projectId, missionId], data);
      void queryClient.invalidateQueries({ queryKey: ['review-versions', projectId, missionId] });
      toast({ title: zh ? '综述大纲已生成并保存为版本' : 'Review outline generated and versioned' });
    },
    onError: (error) => toast({ title: zh ? '无法生成大纲' : 'Could not generate outline', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const save = useMutation({
    mutationFn: (status: ReviewSection['status']) => updateReviewSection(projectId, missionId, current!.id, { expected_version: current!.version, title, purpose, body, citations, claims: current!.claims_json, status }),
    onSuccess: (data) => {
      queryClient.setQueryData(['mission-review', projectId, missionId], data);
      void queryClient.invalidateQueries({ queryKey: ['review-versions', projectId, missionId] });
      toast({ title: zh ? '章节与综述版本已保存' : 'Section and review version saved' });
    },
    onError: (error) => toast({ title: zh ? '章节保存失败' : 'Could not save section', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const generateSection = useMutation({
    mutationFn: () => generateReviewSection(projectId, missionId, current!.id, current!.version, Boolean(current!.body)),
    onSuccess: (run) => {
      setActiveRunId(run.agent_run_id);
      toast({ title: zh ? '章节 Agent 已开始' : 'Section agent started', description: zh ? '将只使用本节勾选论文的阅读卡与解析原文。' : 'It will only use reading cards and parsed source text from selected papers.' });
    },
    onError: (error) => toast({ title: zh ? '无法启动章节 Agent' : 'Could not start section agent', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const activeRun = useQuery({
    queryKey: ['agent-run', projectId, activeRunId],
    queryFn: () => getAgentRun(projectId, activeRunId as string),
    enabled: Boolean(activeRunId),
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1200 : false,
  });
  useEffect(() => {
    if (!activeRunId || !activeRun.data) return;
    if (activeRun.data.status === 'completed') {
      void queryClient.invalidateQueries({ queryKey: ['mission-review', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['review-versions', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['mission-timeline', projectId, missionId] });
      toast({ title: zh ? '章节草稿已生成，等待人工复核' : 'Section draft generated for review' });
      setActiveRunId(null);
    } else if (['failed', 'cancelled'].includes(activeRun.data.status)) {
      toast({ title: zh ? '章节 Agent 未完成' : 'Section agent did not complete', description: activeRun.data.error_json?.message, variant: 'error' });
      setActiveRunId(null);
    }
  }, [activeRun.data, activeRunId, missionId, projectId, queryClient, zh]);
  if (review.isLoading) return <div className="p-8"><Skeleton className="h-[32rem] w-full" /></div>;
  const missing = review.error instanceof ApiError && review.error.status === 404;
  if (missing || !review.data) return <div className="-m-6 flex min-h-[calc(100dvh-3rem)] items-center justify-center bg-bg p-8"><section className="max-w-xl border-y border-border py-12"><ScrollText className="mb-5 h-8 w-8 text-info" /><p className="text-xs font-semibold tracking-[0.16em] text-muted">REVIEW WORKSPACE</p><h1 className="mt-3 text-balance text-3xl font-semibold tracking-[-0.035em] text-text">{zh ? '先把主题簇变成一份可编辑的综述大纲' : 'Turn topic clusters into an editable review outline'}</h1><p className="mt-4 text-sm leading-7 text-muted">{zh ? '章节会绑定当前任务内的论文集合，并在每次编辑时保留不可变版本。' : 'Sections retain mission-scoped paper citations and create an immutable version on every edit.'}</p><div className="mt-7 flex gap-3"><Button onClick={() => generate.mutate()} loading={generate.isPending}>{zh ? '生成结构化大纲' : 'Generate outline'}</Button><Link href={`/projects/${projectId}/missions/${missionId}`} className="inline-flex items-center text-sm text-muted hover:text-text"><ArrowLeft className="mr-1 h-4 w-4" />{zh ? '返回任务' : 'Back to mission'}</Link></div></section></div>;
  const data = review.data;
  return <div className="-m-6 min-h-[calc(100dvh-3rem)] bg-bg">
    <header className="mission-grid border-b border-border bg-surface px-7 pb-7 pt-6">
      <Link href={`/projects/${projectId}/missions/${missionId}`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"><ArrowLeft className="h-3.5 w-3.5" />{zh ? '返回科研任务' : 'Back to mission'}</Link>
      <div className="mt-5 flex flex-wrap items-end justify-between gap-5"><div><div className="flex items-center gap-2"><Badge variant="info" size="sm">review v{data.version}</Badge><span className="text-[10px] text-faint">{data.status}</span></div><h1 className="mt-3 max-w-4xl text-balance text-3xl font-semibold tracking-[-0.035em] text-text">{data.title}</h1></div><div className="flex gap-2"><Link href={`/projects/${projectId}/missions/${missionId}/citations`} className="inline-flex h-10 items-center gap-2 rounded-md border border-border-strong bg-surface px-3 text-xs font-medium text-text hover:bg-surface-2"><FileKey2 className="h-3.5 w-3.5" />{zh ? '引用审计' : 'Citation audit'}</Link><Button variant="secondary" onClick={() => generate.mutate()} loading={generate.isPending}><RefreshCw className="h-3.5 w-3.5" />{zh ? '按当前聚类重建大纲' : 'Rebuild from clusters'}</Button></div></div>
      <div className="mt-6 flex gap-8 border-l-2 border-info/40 pl-5"><Metric label={zh ? '章节' : 'Sections'} value={data.sections.length} /><Metric label={zh ? '引用覆盖' : 'Citation coverage'} value={`${data.citation_coverage.toFixed(1)}%`} /><Metric label={zh ? '待证据主张' : 'Unsupported claims'} value={data.unsupported_claims} /></div>
    </header>
    <div className="grid min-h-[calc(100dvh-17rem)] lg:grid-cols-[17rem_minmax(0,1fr)_19rem]">
      <aside className="border-r border-border bg-surface p-4"><p className="mb-3 text-[10px] font-semibold tracking-[0.12em] text-faint">{zh ? '章节结构' : 'SECTION MAP'}</p><nav className="space-y-1">{data.sections.map((section) => <button key={section.id} onClick={() => setSelectedId(section.id)} className={`w-full border-l-2 px-3 py-2.5 text-left ${current?.id === section.id ? 'border-info bg-info-bg' : 'border-transparent hover:bg-surface-2'}`}><p className="text-xs font-medium text-text">{section.position + 1}. {section.title}</p><p className="mt-1 font-mono text-[9px] text-faint">{section.status} · {section.citations_json.length} cites · v{section.version}</p></button>)}</nav></aside>
      <main className="min-w-0 p-6 lg:p-8">{current && <div className="mx-auto max-w-3xl space-y-5"><div className="flex flex-wrap items-start justify-between gap-3"><div className="flex-1"><Label>{zh ? '章节标题' : 'Section title'}</Label><input value={title} onChange={(event) => setTitle(event.target.value)} className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm font-medium text-text outline-none focus:ring-2 focus:ring-focus/60" /></div><Button variant="secondary" className="mt-6" onClick={() => generateSection.mutate()} loading={generateSection.isPending || Boolean(activeRunId)} disabled={citations.length === 0}><Sparkles className="h-3.5 w-3.5" />{current.body ? (zh ? '重生成证据草稿' : 'Regenerate evidence draft') : (zh ? 'Agent 生成本节' : 'Draft with agent')}</Button></div>{activeRunId && <div className="border-l-2 border-info bg-info-bg px-3 py-2 text-xs text-info">{zh ? `章节 Agent 正在${activeRun.data?.status === 'running' ? '读取证据并写作' : '排队'}；完成后会自动刷新。` : `Section agent is ${activeRun.data?.status ?? 'queued'}; this page will refresh automatically.`}</div>}<div><Label>{zh ? '本节目的' : 'Section purpose'}</Label><textarea value={purpose} onChange={(event) => setPurpose(event.target.value)} rows={3} className="mt-1.5 w-full resize-y rounded-md border border-border-strong bg-surface p-3 text-sm leading-6 text-muted outline-none focus:ring-2 focus:ring-focus/60" /></div><div><div className="mb-1.5 flex items-center justify-between"><Label>{zh ? '章节草稿' : 'Section draft'}</Label><span className="font-mono text-[10px] text-faint">{body.length} chars</span></div><textarea value={body} onChange={(event) => setBody(event.target.value)} rows={18} className="w-full resize-y rounded-md border border-border-strong bg-surface p-4 text-sm leading-7 text-text outline-none focus:ring-2 focus:ring-focus/60" placeholder={zh ? '围绕主题综合多篇论文；没有来源的事实应保留待证据标记。' : 'Synthesize across papers. Keep unsupported facts explicitly marked.'} /></div>{current.claims_json.length > 0 && <section className="border-t border-border pt-4"><div className="mb-3 flex items-center justify-between"><h2 className="text-xs font-semibold text-text">{zh ? '主张—证据审计' : 'Claim–evidence audit'}</h2><span className="font-mono text-[10px] text-faint">{current.claims_json.length} claims</span></div><div className="space-y-2">{current.claims_json.map((claim, index) => { const grounded = claim.evidence_status === 'grounded'; return <article key={index} className="bg-surface-2 p-3"><div className="flex items-start justify-between gap-3"><p className="text-xs leading-5 text-text">{String(claim.text ?? '')}</p><Badge size="sm" variant={grounded ? 'success' : 'warn'}>{grounded ? (zh ? '原文已校验' : 'Grounded') : (zh ? '待补证据' : 'Needs evidence')}</Badge></div>{grounded && <blockquote className="mt-2 border-l border-border-strong pl-3 text-[10px] leading-4 text-muted">“{String(claim.quote ?? '')}”<span className="mt-1 block text-faint">{String(claim.paper_title ?? '')} · §{String(claim.section_seq ?? '')}</span></blockquote>}</article>; })}</div></section>}<div className="flex justify-end gap-2 border-t border-border pt-4"><Button variant="secondary" onClick={() => save.mutate('draft')} loading={save.isPending && save.variables === 'draft'}><Save className="h-3.5 w-3.5" />{zh ? '保存草稿' : 'Save draft'}</Button><Button onClick={() => save.mutate('needs_review')} loading={save.isPending && save.variables === 'needs_review'}><Check className="h-3.5 w-3.5" />{zh ? '提交人工复核' : 'Send for review'}</Button></div></div>}</main>
      <aside className="border-l border-border bg-surface p-4"><h2 className="flex items-center gap-2 text-xs font-semibold text-text"><Quote className="h-3.5 w-3.5 text-info" />{zh ? '本节引用集合' : 'Section citations'}</h2><div className="mt-3 max-h-72 space-y-1 overflow-y-auto">{(papers.data ?? []).map((paper) => <label key={paper.paper_id} className="flex cursor-pointer gap-2 rounded-md p-2 hover:bg-surface-2"><input type="checkbox" checked={citations.includes(paper.paper_id)} onChange={(event) => setCitations((items) => event.target.checked ? [...items, paper.paper_id] : items.filter((id) => id !== paper.paper_id))} className="mt-0.5" /><span className="line-clamp-2 text-[10px] leading-4 text-muted">{paper.title}</span></label>)}</div><section className="mt-6 border-t border-border pt-4"><h2 className="flex items-center gap-2 text-xs font-semibold text-text"><History className="h-3.5 w-3.5 text-info" />{zh ? '版本历史' : 'Version history'}</h2><div className="mt-3 space-y-2">{(versions.data ?? []).slice(0, 12).map((version) => <div key={version.id} className="flex items-center justify-between bg-surface-2 px-2.5 py-2"><div><p className="font-mono text-[10px] text-text">v{version.version}</p><p className="text-[9px] text-faint">{version.source_type}</p></div><FileClock className="h-3.5 w-3.5 text-faint" /></div>)}</div></section><Link href={`/projects/${projectId}/paper`} className="mt-5 flex items-center gap-2 border-t border-border pt-4 text-xs font-medium text-info hover:underline"><BookOpen className="h-3.5 w-3.5" />{zh ? '打开论文工作区' : 'Open Paper Workspace'}</Link></aside>
    </div>
  </div>;
}

function Metric({ label, value }: { label: string; value: string | number }) { return <div><p className="font-mono text-lg font-semibold tabular-nums text-text">{value}</p><p className="mt-0.5 text-[10px] text-muted">{label}</p></div>; }
