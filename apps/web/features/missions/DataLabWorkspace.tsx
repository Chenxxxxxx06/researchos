'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, Braces, Database, History, Play, Plus, ShieldCheck, Sparkles, Table2 } from 'lucide-react';
import Link from 'next/link';
import { useEffect, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import { getAgentRun } from '@/lib/api/agents';
import { createDatasetSource, listDatasetSources, listSqlResults, runSqlQuestion, type DatasetColumn } from '@/lib/api/dataLab';
import { useI18n } from '@/lib/i18n';

const sample = JSON.stringify([
  { method: 'baseline', score: 0.71, seed: 1 },
  { method: 'proposed', score: 0.79, seed: 1 },
], null, 2);

export function DataLabWorkspace({ projectId, missionId }: { projectId: string; missionId: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const queryClient = useQueryClient();
  const sources = useQuery({ queryKey: ['dataset-sources', projectId], queryFn: () => listDatasetSources(projectId) });
  const results = useQuery({ queryKey: ['sql-results', projectId, missionId], queryFn: () => listSqlResults(projectId, missionId) });
  const [selected, setSelected] = useState('');
  const [question, setQuestion] = useState('比较各方法的平均 score，并按结果降序排列');
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [rowsText, setRowsText] = useState(sample);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  useEffect(() => {
    if (!selected && sources.data?.[0]) setSelected(sources.data[0].id);
  }, [selected, sources.data]);
  const current = sources.data?.find((item) => item.id === selected);
  const currentResults = useMemo(() => (results.data ?? []).filter((item) => item.dataset_source_id === selected), [results.data, selected]);
  const create = useMutation({
    mutationFn: () => {
      const rows = JSON.parse(rowsText) as Array<Record<string, unknown>>;
      if (!Array.isArray(rows) || !rows.length || rows.some((row) => !row || Array.isArray(row) || typeof row !== 'object')) throw new Error(zh ? '必须粘贴至少一行 JSON 对象数组。' : 'Paste a non-empty JSON array of objects.');
      const normalizedRows = normalizeRows(rows);
      const columns = inferColumns(normalizedRows);
      return createDatasetSource(projectId, { name, description, columns, rows: normalizedRows });
    },
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ['dataset-sources', projectId] });
      setSelected(data.id);
      setShowCreate(false);
      toast({ title: zh ? '数据快照已注册' : 'Dataset snapshot registered' });
    },
    onError: (error) => toast({ title: zh ? '数据注册失败' : 'Could not register dataset', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const run = useMutation({
    mutationFn: () => runSqlQuestion(projectId, missionId, selected, question),
    onSuccess: (handle) => {
      setActiveRunId(handle.agent_run_id);
      toast({ title: zh ? '只读 SQL Agent 已启动' : 'Read-only SQL Agent started' });
    },
    onError: (error) => toast({ title: zh ? 'SQL Agent 启动失败' : 'Could not start SQL Agent', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  const activeRun = useQuery({ queryKey: ['agent-run', projectId, activeRunId], queryFn: () => getAgentRun(projectId, activeRunId as string), enabled: Boolean(activeRunId), refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1000 : false });
  useEffect(() => {
    if (!activeRunId || !activeRun.data) return;
    if (activeRun.data.status === 'completed') {
      void queryClient.invalidateQueries({ queryKey: ['sql-results', projectId, missionId] });
      void queryClient.invalidateQueries({ queryKey: ['mission-timeline', projectId, missionId] });
      setActiveRunId(null);
      toast({ title: zh ? 'SQL 结果已保存' : 'SQL result saved' });
    } else if (['failed', 'cancelled'].includes(activeRun.data.status)) {
      toast({ title: zh ? 'SQL Agent 未完成' : 'SQL Agent did not complete', description: activeRun.data.error_json?.message, variant: 'error' });
      setActiveRunId(null);
    }
  }, [activeRun.data, activeRunId, missionId, projectId, queryClient, zh]);
  if (sources.isLoading || results.isLoading) return <div className="p-8"><Skeleton className="h-[34rem] w-full" /></div>;
  const latest = currentResults[0];
  return <div className="-m-5 min-h-[calc(100dvh-4rem)] bg-bg lg:-m-6 xl:-m-8">
    <header className="border-b border-border bg-surface px-7 py-6"><Link href={`/projects/${projectId}/missions/${missionId}/experiment-plan`} className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"><ArrowLeft className="h-3.5 w-3.5" />{zh ? '返回实验方案' : 'Back to experiment plan'}</Link><div className="mt-5 flex flex-wrap items-end justify-between gap-4"><div><div className="flex items-center gap-2"><Badge variant="info" size="sm">READ-ONLY DATA LAB</Badge><ShieldCheck className="h-4 w-4 text-success" /></div><h1 className="mt-3 text-3xl font-semibold tracking-[-0.035em] text-text">{zh ? '用自然语言查询实验数据' : 'Query experiment data in natural language'}</h1><p className="mt-2 text-sm text-muted">{zh ? '数据只在隔离的内存 SQLite 快照中执行；仅允许单条 SELECT/WITH 查询。' : 'Queries run against an isolated in-memory SQLite snapshot; only one SELECT/WITH statement is allowed.'}</p></div><Button variant="secondary" onClick={() => setShowCreate(!showCreate)}><Plus className="h-3.5 w-3.5" />{zh ? '注册 JSON 数据' : 'Register JSON data'}</Button></div></header>
    {showCreate && <section className="border-b border-border bg-info-bg/35 p-6"><div className="mx-auto grid max-w-5xl gap-4 lg:grid-cols-[18rem_1fr]"><div><Label>{zh ? '数据集名称' : 'Dataset name'}</Label><input className="mt-1.5 h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm" value={name} onChange={(e) => setName(e.target.value)} /><Label className="mt-4 block">{zh ? '说明' : 'Description'}</Label><textarea className="mt-1.5 w-full rounded-md border border-border-strong bg-surface p-3 text-xs" rows={5} value={description} onChange={(e) => setDescription(e.target.value)} /></div><div><Label>{zh ? 'JSON 对象数组（最多 5000 行）' : 'JSON object array (up to 5,000 rows)'}</Label><textarea className="mt-1.5 w-full rounded-md border border-border-strong bg-surface p-3 font-mono text-xs" rows={10} value={rowsText} onChange={(e) => setRowsText(e.target.value)} /><div className="mt-2 flex justify-end"><Button onClick={() => create.mutate()} loading={create.isPending} disabled={!name.trim()}>{zh ? '注册只读快照' : 'Register snapshot'}</Button></div></div></div></section>}
    <div className="grid min-h-[calc(100dvh-14rem)] lg:grid-cols-[17rem_minmax(0,1fr)]"><aside className="border-r border-border bg-surface p-4"><p className="mb-3 text-[10px] font-semibold tracking-[0.12em] text-faint">DATASETS</p>{(sources.data ?? []).length === 0 ? <p className="text-xs leading-5 text-muted">{zh ? '尚未注册数据。先用上方按钮粘贴 JSON 结果或实验指标。' : 'No data yet. Register JSON results or experiment metrics above.'}</p> : <div className="space-y-1">{sources.data?.map((source) => <button key={source.id} onClick={() => setSelected(source.id)} className={`w-full border-l-2 px-3 py-2.5 text-left ${selected === source.id ? 'border-info bg-info-bg' : 'border-transparent hover:bg-surface-2'}`}><p className="text-xs font-medium text-text">{source.name}</p><p className="mt-1 font-mono text-[9px] text-faint">{source.rows_json.length} rows · {source.columns_json.length} cols</p></button>)}</div>}<section className="mt-7 border-t border-border pt-4"><h2 className="flex items-center gap-2 text-xs font-semibold text-text"><History className="h-3.5 w-3.5" />{zh ? '查询历史' : 'History'}</h2><div className="mt-2 space-y-1">{currentResults.slice(0, 12).map((result) => <button key={result.id} className="w-full p-2 text-left hover:bg-surface-2"><p className="line-clamp-2 text-[10px] text-muted">{result.question}</p><p className="mt-1 font-mono text-[9px] text-faint">{result.row_count} rows</p></button>)}</div></section></aside><main className="p-6 lg:p-8"><div className="mx-auto max-w-5xl"><section className="border-b border-border pb-6"><div className="flex items-center gap-2"><Database className="h-4 w-4 text-info" /><h2 className="text-sm font-semibold text-text">{current?.name ?? (zh ? '选择数据集' : 'Select a dataset')}</h2></div>{current && <div className="mt-3 flex flex-wrap gap-2">{current.columns_json.map((column) => <span key={column.name} className="bg-surface-2 px-2 py-1 font-mono text-[10px] text-muted">{column.name}:{column.type}</span>)}</div>}<Label className="mt-5 block">{zh ? '数据问题' : 'Question'}</Label><textarea rows={4} value={question} onChange={(e) => setQuestion(e.target.value)} className="mt-1.5 w-full rounded-md border border-border-strong bg-surface p-3 text-sm leading-6 text-text outline-none focus:ring-2 focus:ring-focus/60" /><div className="mt-3 flex justify-end"><Button onClick={() => run.mutate()} disabled={!selected || !question.trim()} loading={run.isPending || Boolean(activeRunId)}><Sparkles className="h-3.5 w-3.5" />{activeRunId ? `${activeRun.data?.status ?? 'queued'}…` : (zh ? '生成并执行只读 SQL' : 'Generate and run read-only SQL')}</Button></div></section>{latest ? <section className="pt-6"><div className="flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold text-text"><Table2 className="h-4 w-4 text-info" />{zh ? '最近结果' : 'Latest result'}</h2><Badge size="sm" variant="success">{latest.row_count} rows</Badge></div><pre className="mt-3 overflow-x-auto border-l-2 border-info bg-info-bg p-3 font-mono text-xs text-info">{latest.sql}</pre><div className="mt-4 overflow-x-auto border border-border"><table className="w-full text-left text-xs"><thead className="bg-surface-2"> <tr>{latest.columns_json.map((column) => <th key={column} className="px-3 py-2 font-medium text-muted">{column}</th>)}</tr></thead><tbody>{latest.rows_json.map((row, index) => <tr key={index} className="border-t border-border">{row.map((cell, cursor) => <td key={cursor} className="px-3 py-2 text-text">{String(cell ?? '')}</td>)}</tr>)}</tbody></table></div></section> : <section className="flex min-h-64 items-center justify-center text-center"><div><Braces className="mx-auto h-7 w-7 text-faint" /><p className="mt-3 text-sm text-muted">{zh ? '查询结果将保留 SQL、列、行数和 AgentRun。' : 'Results preserve SQL, columns, row count, and AgentRun.'}</p></div></section>}</div></main></div>
  </div>;
}

function inferColumns(rows: Array<Record<string, unknown>>): DatasetColumn[] {
  const keys = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));
  return keys.map((name) => {
    const value = rows.find((row) => row[name] != null)?.[name];
    const type: DatasetColumn['type'] = typeof value === 'boolean' ? 'boolean' : typeof value === 'number' ? (Number.isInteger(value) ? 'integer' : 'real') : 'text';
    return { name, type };
  });
}

function normalizeRows(rows: Array<Record<string, unknown>>) {
  const mapping = new Map<string, string>();
  for (const key of Array.from(new Set(rows.flatMap((row) => Object.keys(row))))) {
    let normalized = key.replace(/[^A-Za-z0-9_]/g, '_').replace(/^([^A-Za-z_])/, '_$1');
    let suffix = 2;
    while ([...mapping.values()].includes(normalized)) normalized = `${normalized}_${suffix++}`;
    mapping.set(key, normalized);
  }
  return rows.map((row) => Object.fromEntries(Object.entries(row).map(([key, value]) => [mapping.get(key)!, value])));
}
