'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowRight,
  BookOpen,
  Check,
  FileSearch,
  FolderTree,
  LibraryBig,
  Plus,
  Save,
  Search,
  Sparkles,
} from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import {
  addMissionPapers,
  generateReadingCard,
  generateTopicClusters,
  listMissionPapers,
  listReadingCards,
  listTopicClusters,
  ragSearch,
  saveReadingCard,
  type RagHit,
  type RagSearchResponse,
  type ReadingCard,
} from '@/lib/api/knowledge';
import { getAgentRun } from '@/lib/api/agents';

export function LiteratureStagePanel({
  projectId,
  missionId,
  lang,
}: {
  projectId: string;
  missionId: string;
  lang: 'zh' | 'en';
}) {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<RagHit[]>([]);
  const [searchMeta, setSearchMeta] = useState<RagSearchResponse | null>(null);
  const papers = useQuery({
    queryKey: ['mission-papers', projectId, missionId],
    queryFn: () => listMissionPapers(projectId, missionId),
  });
  const clusters = useQuery({
    queryKey: ['mission-clusters', projectId, missionId],
    queryFn: () => listTopicClusters(projectId, missionId),
  });
  const search = useMutation({
    mutationFn: () => ragSearch(projectId, query.trim()),
    onSuccess: (data) => {
      setResults(uniquePaperHits(data.hits));
      setSearchMeta(data);
    },
    onError: (error) => toast({ title: lang === 'zh' ? '检索失败' : 'Search failed', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const add = useMutation({
    mutationFn: (paperId: string) => addMissionPapers(projectId, missionId, [paperId]),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mission-papers', projectId, missionId] });
      toast({ title: lang === 'zh' ? '论文已纳入任务' : 'Paper included' });
    },
  });
  const cluster = useMutation({
    mutationFn: () => generateTopicClusters(projectId, missionId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['mission-clusters', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['mission-papers', projectId, missionId] });
      toast({ title: lang === 'zh' ? '主题簇已生成，可继续人工调整' : 'Reviewable clusters generated' });
    },
    onError: (error) => toast({ title: lang === 'zh' ? '无法生成主题簇' : 'Could not cluster papers', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const included = new Set((papers.data ?? []).map((paper) => paper.paper_id));

  return (
    <div className="space-y-7">
      <section>
        <div className="mb-3 flex items-end justify-between gap-4">
          <div>
            <h3 className="text-sm font-semibold text-text">{lang === 'zh' ? '从项目论文库检索证据片段' : 'Search evidence in the project library'}</h3>
            <p className="mt-1 text-xs leading-5 text-muted">{lang === 'zh' ? '结果精确到论文段落；纳入后才进入本任务的证据边界。' : 'Results point to paper sections. Include a paper to bring it into this mission.'}</p>
          </div>
          <Badge variant="neutral" size="sm">RAG · vector + keyword</Badge>
        </div>
        <form
          className="flex gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (query.trim().length >= 2) search.mutate();
          }}
        >
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} className="h-10 w-full rounded-md border border-border-strong bg-bg pl-9 pr-3 text-sm text-text outline-none focus:ring-2 focus:ring-focus/60" placeholder={lang === 'zh' ? '输入方法、问题或实验关键词' : 'Search methods, questions, or experiments'} />
          </div>
          <Button type="submit" loading={search.isPending} disabled={query.trim().length < 2}>{lang === 'zh' ? '检索' : 'Search'}</Button>
        </form>
        {results.length > 0 && (
          <div className="mt-4 divide-y divide-border border-y border-border">
            {results.map((hit) => (
              <article key={`${hit.paper_id}-${hit.section_id ?? 'abstract'}`} className="grid gap-3 py-4 md:grid-cols-[minmax(0,1fr)_auto]">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h4 className="text-sm font-medium text-text">{hit.title}</h4>
                    <span className="font-mono text-[10px] text-faint">{hit.score.toFixed(2)}</span>
                  </div>
                  <p className="mt-1 text-[11px] font-medium text-info">{hit.heading} · {hit.citation_key}</p>
                  <p className="mt-2 line-clamp-3 text-xs leading-5 text-muted">{hit.snippet}</p>
                </div>
                <Button variant="secondary" size="sm" disabled={included.has(hit.paper_id)} loading={add.isPending && add.variables === hit.paper_id} onClick={() => add.mutate(hit.paper_id)}>
                  {included.has(hit.paper_id) ? <Check className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />}
                  {included.has(hit.paper_id) ? (lang === 'zh' ? '已纳入' : 'Included') : (lang === 'zh' ? '纳入任务' : 'Include')}
                </Button>
              </article>
            ))}
          </div>
        )}
        {searchMeta && (
          <p className="mt-2 font-mono text-[10px] text-faint">
            {searchMeta.embedding_model} · {searchMeta.mode}
            {searchMeta.indexed_papers > 0 && ` · indexed ${searchMeta.indexed_papers} paper(s) / ${searchMeta.indexed_chunks} chunks`}
          </p>
        )}
      </section>

      <section className="grid gap-5 lg:grid-cols-[minmax(0,1.2fr)_minmax(18rem,0.8fr)]">
        <div className="border-t border-border pt-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-text"><LibraryBig className="h-4 w-4 text-info" />{lang === 'zh' ? `已纳入论文（${papers.data?.length ?? 0}）` : `Included papers (${papers.data?.length ?? 0})`}</h3>
            <Link href={`/projects/${projectId}/research`} className="text-xs font-medium text-info hover:underline">{lang === 'zh' ? '打开完整论文库' : 'Open library'}</Link>
          </div>
          {papers.isLoading && <Skeleton className="h-36 w-full" />}
          <div className="divide-y divide-border">
            {(papers.data ?? []).map((paper) => (
              <Link key={paper.id} href={`/projects/${projectId}/research/read/${paper.paper_id}?mission=${missionId}`} className="group flex items-start justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-text group-hover:text-info">{paper.title}</p>
                  <p className="mt-1 text-[10px] text-faint">{paper.venue ?? '—'} · {paper.ingest_status}</p>
                </div>
                <ArrowRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint" />
              </Link>
            ))}
            {!papers.isLoading && (papers.data?.length ?? 0) === 0 && <p className="py-6 text-xs text-muted">{lang === 'zh' ? '先检索并纳入论文，随后生成主题簇。' : 'Search and include papers before clustering.'}</p>}
          </div>
        </div>

        <div className="border-t border-border pt-5">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="flex items-center gap-2 text-sm font-semibold text-text"><FolderTree className="h-4 w-4 text-info" />{lang === 'zh' ? '主题聚类' : 'Topic clusters'}</h3>
            <Button variant="secondary" size="sm" loading={cluster.isPending} disabled={(papers.data?.length ?? 0) === 0} onClick={() => cluster.mutate()}>{lang === 'zh' ? '生成/重建' : 'Generate'}</Button>
          </div>
          <div className="space-y-2">
            {(clusters.data ?? []).map((item) => (
              <div key={item.id} className="border-l-2 border-info/35 bg-surface-2 px-3 py-2.5">
                <div className="flex items-center justify-between gap-2"><p className="text-xs font-medium text-text">{item.name}</p><span className="font-mono text-[10px] text-faint">{item.paper_count}</span></div>
                <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">{item.keywords_json.join(' · ') || item.summary}</p>
              </div>
            ))}
            {!clusters.isLoading && (clusters.data?.length ?? 0) === 0 && <p className="py-4 text-xs text-muted">{lang === 'zh' ? '尚未形成主题簇。生成后结果会持久保存。' : 'No clusters yet. Generated clusters are persisted.'}</p>}
          </div>
        </div>
      </section>
    </div>
  );
}

export function ReadingStagePanel({ projectId, missionId, lang }: { projectId: string; missionId: string; lang: 'zh' | 'en' }) {
  const queryClient = useQueryClient();
  const papers = useQuery({ queryKey: ['mission-papers', projectId, missionId], queryFn: () => listMissionPapers(projectId, missionId) });
  const cards = useQuery({ queryKey: ['reading-cards', projectId, missionId], queryFn: () => listReadingCards(projectId, missionId) });
  const [selected, setSelected] = useState('');
  const [summary, setSummary] = useState('');
  const [question, setQuestion] = useState('');
  const [method, setMethod] = useState('');
  const [strengths, setStrengths] = useState('');
  const [limitations, setLimitations] = useState('');
  const [reproducibility, setReproducibility] = useState('');
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const current = useMemo(() => cards.data?.find((card) => card.paper_id === selected), [cards.data, selected]);

  useEffect(() => {
    if (!selected && papers.data?.[0]) setSelected(papers.data[0].paper_id);
  }, [papers.data, selected]);
  useEffect(() => {
    setSummary(current?.summary ?? '');
    setQuestion(current?.research_question ?? '');
    setMethod((current?.method_flow_json ?? []).join('\n'));
    setStrengths((current?.strengths_json ?? []).join('\n'));
    setLimitations((current?.limitations_json ?? []).join('\n'));
    setReproducibility((current?.reproducibility_json ?? []).join('\n'));
  }, [current]);

  const save = useMutation({
    mutationFn: (status: ReadingCard['status']) => saveReadingCard(projectId, selected, {
      mission_id: missionId,
      expected_version: current?.version,
      summary,
      research_question: question,
      method_flow: lines(method),
      strengths: lines(strengths),
      limitations: lines(limitations),
      reproducibility: lines(reproducibility),
      claims: current?.claims_json ?? [],
      status,
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reading-cards', projectId, missionId] });
      toast({ title: lang === 'zh' ? '阅读卡已保存' : 'Reading card saved' });
    },
    onError: (error) => toast({ title: lang === 'zh' ? '保存失败' : 'Save failed', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const generate = useMutation({
    mutationFn: () => generateReadingCard(projectId, selected, missionId, Boolean(current)),
    onSuccess: (run) => {
      setActiveRunId(run.agent_run_id);
      toast({ title: lang === 'zh' ? '阅读卡 Agent 已开始' : 'Reading-card agent started', description: lang === 'zh' ? '它会只使用已解析原文，并逐条校验引用片段。' : 'It will use parsed source text and validate every evidence quote.' });
    },
    onError: (error) => toast({ title: lang === 'zh' ? '无法启动阅读卡 Agent' : 'Could not start the reading-card agent', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
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
      void queryClient.invalidateQueries({ queryKey: ['reading-cards', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['mission-timeline', projectId, missionId] });
      toast({ title: lang === 'zh' ? '阅读卡已生成，等待人工复核' : 'Reading card generated for review' });
      setActiveRunId(null);
    } else if (['failed', 'cancelled'].includes(activeRun.data.status)) {
      toast({ title: lang === 'zh' ? '阅读卡 Agent 未完成' : 'Reading-card agent did not complete', description: activeRun.data.error_json?.message, variant: 'error' });
      setActiveRunId(null);
    }
  }, [activeRun.data, activeRunId, lang, missionId, projectId, queryClient]);

  if (papers.isLoading || cards.isLoading) return <Skeleton className="h-80 w-full" />;
  if ((papers.data?.length ?? 0) === 0) return <div className="flex min-h-60 flex-col items-start justify-center border-y border-dashed border-border"><BookOpen className="mb-3 h-6 w-6 text-faint" /><p className="text-sm text-muted">{lang === 'zh' ? '请先在“文献与聚类”阶段纳入论文。' : 'Include papers in the literature step first.'}</p></div>;

  return (
    <div className="grid gap-6 lg:grid-cols-[17rem_minmax(0,1fr)]">
      <aside className="border-r border-border pr-4">
        <div className="mb-3 flex items-center justify-between"><h3 className="text-xs font-semibold text-text">{lang === 'zh' ? '核心论文' : 'Core papers'}</h3><span className="font-mono text-[10px] text-faint">{cards.data?.length ?? 0}/{papers.data?.length ?? 0}</span></div>
        <div className="space-y-1">
          {(papers.data ?? []).map((paper) => {
            const card = cards.data?.find((item) => item.paper_id === paper.paper_id);
            return <button key={paper.id} type="button" onClick={() => setSelected(paper.paper_id)} className={`w-full rounded-md border-l-2 px-3 py-2.5 text-left ${selected === paper.paper_id ? 'border-info bg-info-bg' : 'border-transparent hover:bg-surface-2'}`}><p className="line-clamp-2 text-xs font-medium leading-5 text-text">{paper.title}</p><p className="mt-1 text-[10px] text-faint">{card ? (card.status === 'reviewed' ? (lang === 'zh' ? '已复核' : 'Reviewed') : (lang === 'zh' ? '草稿' : 'Draft')) : (lang === 'zh' ? '未建卡' : 'No card')}</p></button>;
          })}
        </div>
      </aside>
      <div className="min-w-0 space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div><h3 className="text-sm font-semibold text-text">{papers.data?.find((paper) => paper.paper_id === selected)?.title}</h3><p className="mt-1 text-[10px] text-faint">{current ? `card v${current.version} · ${current.status}` : (lang === 'zh' ? '尚未生成阅读卡' : 'No reading card yet')}</p></div>
          <div className="flex items-center gap-2">
            <Button variant="secondary" size="sm" onClick={() => generate.mutate()} loading={generate.isPending || Boolean(activeRunId)}><Sparkles className="h-3.5 w-3.5" />{current ? (lang === 'zh' ? '重新生成新版本' : 'Regenerate version') : (lang === 'zh' ? 'Agent 生成' : 'Generate with agent')}</Button>
            <Link href={`/projects/${projectId}/research/read/${selected}?mission=${missionId}`} className="flex items-center gap-1 text-xs font-medium text-info hover:underline"><FileSearch className="h-3.5 w-3.5" />{lang === 'zh' ? '查看原文与笔记' : 'Open paper and notes'}</Link>
          </div>
        </div>
        <Field label={lang === 'zh' ? '核心摘要' : 'Core summary'} value={summary} onChange={setSummary} rows={4} placeholder={lang === 'zh' ? '用自己的语言说明论文做了什么，避免复制摘要。' : 'Explain the paper in your own words.'} />
        <Field label={lang === 'zh' ? '研究问题' : 'Research question'} value={question} onChange={setQuestion} rows={3} />
        <div className="grid gap-4 md:grid-cols-2">
          <Field label={lang === 'zh' ? '方法流程（每行一步）' : 'Method flow (one step per line)'} value={method} onChange={setMethod} rows={6} />
          <Field label={lang === 'zh' ? '可复现要点（每行一项）' : 'Reproducibility (one per line)'} value={reproducibility} onChange={setReproducibility} rows={6} />
          <Field label={lang === 'zh' ? '优点' : 'Strengths'} value={strengths} onChange={setStrengths} rows={5} />
          <Field label={lang === 'zh' ? '局限' : 'Limitations'} value={limitations} onChange={setLimitations} rows={5} />
        </div>
        {(current?.claims_json.length ?? 0) > 0 && (
          <section className="border-y border-border py-4">
            <div className="mb-3 flex items-center justify-between"><h4 className="text-xs font-semibold text-text">{lang === 'zh' ? '主张与原文证据' : 'Claims and source evidence'}</h4><span className="font-mono text-[10px] text-faint">{current?.claims_json.length}</span></div>
            <div className="space-y-3">
              {current?.claims_json.map((claim, index) => {
                const grounded = claim.evidence_status === 'grounded';
                return <article key={`${String(claim.section_id ?? 'missing')}-${index}`} className={`border-l-2 px-3 py-2 ${grounded ? 'border-success bg-success-bg/45' : 'border-warn bg-warn-bg/45'}`}><div className="flex items-start justify-between gap-3"><p className="text-xs leading-5 text-text">{String(claim.text ?? '')}</p><Badge variant={grounded ? 'success' : 'warn'} size="sm">{grounded ? (lang === 'zh' ? '已定位' : 'Grounded') : (lang === 'zh' ? '待证据' : 'Needs evidence')}</Badge></div>{claim.quote ? <p className="mt-2 line-clamp-3 border-l border-border-strong pl-2 text-[10px] italic leading-4 text-muted">“{String(claim.quote)}”</p> : null}<p className="mt-1 font-mono text-[9px] text-faint">{claim.heading ? `${String(claim.heading)} · ` : ''}{claim.section_seq != null ? `S${String(claim.section_seq)}` : ''}</p></article>;
              })}
            </div>
          </section>
        )}
        <div className="flex flex-wrap justify-end gap-2 border-t border-border pt-4">
          <Button variant="secondary" onClick={() => save.mutate('draft')} loading={save.isPending && save.variables === 'draft'}><Save className="h-3.5 w-3.5" />{lang === 'zh' ? '保存草稿' : 'Save draft'}</Button>
          <Button onClick={() => save.mutate('reviewed')} loading={save.isPending && save.variables === 'reviewed'}><Check className="h-3.5 w-3.5" />{lang === 'zh' ? '保存并标记已复核' : 'Save as reviewed'}</Button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, rows, placeholder }: { label: string; value: string; onChange: (value: string) => void; rows: number; placeholder?: string }) {
  return <div><Label>{label}</Label><textarea value={value} onChange={(event) => onChange(event.target.value)} rows={rows} placeholder={placeholder} className="mt-1.5 w-full resize-y rounded-md border border-border-strong bg-bg p-3 text-sm leading-6 text-text outline-none placeholder:text-faint focus:ring-2 focus:ring-focus/60" /></div>;
}

function lines(value: string) {
  return value.split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

function uniquePaperHits(hits: RagHit[]) {
  const seen = new Set<string>();
  return hits.filter((hit) => {
    if (seen.has(hit.paper_id)) return false;
    seen.add(hit.paper_id);
    return true;
  });
}
