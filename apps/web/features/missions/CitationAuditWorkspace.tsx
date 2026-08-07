'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, ArrowLeft, CheckCircle2, Copy, Download, FileKey2, GitMerge, RefreshCw, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import { getAgentRun } from '@/lib/api/agents';
import { listCitationAudits, runCitationAudit } from '@/lib/api/citationAudits';
import { useI18n } from '@/lib/i18n';

export function CitationAuditWorkspace({ projectId, missionId }: { projectId: string; missionId: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const queryClient = useQueryClient();
  const audits = useQuery({ queryKey: ['citation-audits', projectId, missionId], queryFn: () => listCitationAudits(projectId, missionId) });
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const run = useMutation({
    mutationFn: () => runCitationAudit(projectId, missionId),
    onSuccess: (handle) => { setActiveRunId(handle.agent_run_id); toast({ title: zh ? '引用整理 Agent 已启动' : 'Citation organizer started' }); },
    onError: (error) => toast({ title: zh ? '无法启动引用审计' : 'Could not start citation audit', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const activeRun = useQuery({ queryKey: ['agent-run', projectId, activeRunId], queryFn: () => getAgentRun(projectId, activeRunId as string), enabled: Boolean(activeRunId), refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1000 : false });
  useEffect(() => {
    if (!activeRunId || !activeRun.data) return;
    if (activeRun.data.status === 'completed') {
      void queryClient.invalidateQueries({ queryKey: ['citation-audits', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['mission-timeline', projectId, missionId] });
      setActiveRunId(null);
      toast({ title: zh ? '引用审计与 BibTeX 已生成' : 'Citation audit and BibTeX generated' });
    } else if (['failed', 'cancelled'].includes(activeRun.data.status)) {
      toast({ title: zh ? '引用整理 Agent 未完成' : 'Citation organizer did not complete', description: activeRun.data.error_json?.message, variant: 'error' });
      setActiveRunId(null);
    }
  }, [activeRun.data, activeRunId, missionId, projectId, queryClient, zh]);
  if (audits.isLoading) return <div className="p-8"><Skeleton className="h-[34rem] w-full" /></div>;
  const audit = audits.data?.[0];
  return <div className="-m-6 min-h-[calc(100dvh-3.5rem)] bg-bg"><header className="border-b border-border bg-surface px-7 py-6"><Link href={`/projects/${projectId}/missions/${missionId}/review`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"><ArrowLeft className="h-3.5 w-3.5" />{zh ? '返回综述' : 'Back to review'}</Link><div className="mt-5 flex flex-wrap items-end justify-between gap-5"><div><Badge variant="info" size="sm">CITATION ORGANIZER</Badge><h1 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-text">{zh ? '引用元数据、重复项与 BibTeX 审计' : 'Citation metadata, duplicates, and BibTeX audit'}</h1><p className="mt-2 text-sm text-muted">{zh ? '只整理任务内真实论文，不补造作者、年份、期刊或 DOI。' : 'Organizes real mission papers only; missing authors, years, venues, and identifiers are never invented.'}</p></div><Button onClick={() => run.mutate()} loading={run.isPending || Boolean(activeRunId)}><Sparkles className="h-3.5 w-3.5" />{activeRunId ? `${activeRun.data?.status ?? 'queued'}…` : audit ? (zh ? '重新审计' : 'Run again') : (zh ? '运行引用整理 Agent' : 'Run organizer')}</Button></div>{audit && <div className="mt-6 flex gap-8 border-l-2 border-info/50 pl-5"><Metric label={zh ? '论文' : 'Papers'} value={audit.items_json.length} /><Metric label={zh ? '缺失字段' : 'Missing fields'} value={audit.missing_field_count} /><Metric label={zh ? '疑似重复组' : 'Duplicate groups'} value={audit.duplicate_groups_json.length} /><Metric label={zh ? '审计历史' : 'Audit history'} value={audits.data?.length ?? 0} /></div>}</header>{audit ? <div className="grid lg:grid-cols-[minmax(0,1fr)_24rem]"><main className="p-6 lg:p-8"><div className="space-y-2">{audit.items_json.map((item) => <article key={item.paper_id} className="grid gap-3 border-l-2 border-border bg-surface p-4 md:grid-cols-[minmax(0,1fr)_13rem]"><div><div className="flex items-start gap-2"><code className="shrink-0 bg-surface-2 px-1.5 py-0.5 text-[10px] text-info">{item.citation_key}</code><h2 className="text-xs font-medium leading-5 text-text">{item.title}</h2></div><p className="mt-2 text-[10px] text-muted">{item.authors.join(', ') || (zh ? '作者缺失' : 'Authors missing')} · {item.year ?? 'n.d.'} · {item.venue ?? item.arxiv_id ?? '—'}</p></div><div className="flex flex-wrap items-start justify-end gap-1">{item.status === 'complete' ? <Badge variant="success" size="sm"><CheckCircle2 className="h-3 w-3" />{zh ? '完整' : 'Complete'}</Badge> : item.missing_fields.map((field) => <Badge key={field} variant="warn" size="sm">{field}</Badge>)}</div></article>)}</div>{audit.duplicate_groups_json.length > 0 && <section className="mt-7 border-t border-border pt-5"><h2 className="flex items-center gap-2 text-sm font-semibold text-text"><GitMerge className="h-4 w-4 text-warn" />{zh ? '疑似重复项' : 'Possible duplicates'}</h2>{audit.duplicate_groups_json.map((group) => <div key={group.match_key} className="mt-2 bg-warn-bg p-3 text-xs text-warn">{group.match_key} · {group.count} records</div>)}</section>}</main><aside className="border-l border-border bg-surface p-5"><div className="flex items-center justify-between"><h2 className="flex items-center gap-2 text-xs font-semibold text-text"><FileKey2 className="h-4 w-4 text-info" />BibTeX</h2><div className="flex gap-1"><Button size="icon" variant="ghost" title="Copy" onClick={() => { void navigator.clipboard.writeText(audit.bibtex_text); toast({ title: zh ? '已复制 BibTeX' : 'BibTeX copied' }); }}><Copy className="h-3.5 w-3.5" /></Button><Button size="icon" variant="ghost" title="Download" onClick={() => downloadBibtex(audit.bibtex_text)}><Download className="h-3.5 w-3.5" /></Button></div></div><textarea readOnly value={audit.bibtex_text} rows={30} className="mt-3 w-full resize-y rounded-md border border-border-strong bg-bg p-3 font-mono text-[10px] leading-5 text-muted" /><p className="mt-3 flex gap-2 text-[10px] leading-4 text-faint"><AlertTriangle className="h-3.5 w-3.5 shrink-0 text-warn" />{zh ? '黄色字段必须从可信来源人工补齐；审计不会猜测。' : 'Yellow fields require trusted manual metadata; the organizer never guesses.'}</p></aside></div> : <div className="flex min-h-[28rem] items-center justify-center text-center"><div><RefreshCw className="mx-auto h-7 w-7 text-faint" /><p className="mt-3 text-sm text-muted">{zh ? '运行一次引用整理 Agent，生成可下载的审计结果。' : 'Run the organizer to create a downloadable audit.'}</p></div></div>}</div>;
}

function Metric({ label, value }: { label: string; value: number }) { return <div><p className="font-mono text-lg font-semibold text-text">{value}</p><p className="text-[10px] text-muted">{label}</p></div>; }
function downloadBibtex(content: string) { const url = URL.createObjectURL(new Blob([content], { type: 'application/x-bibtex' })); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'mission-references.bib'; anchor.click(); URL.revokeObjectURL(url); }
