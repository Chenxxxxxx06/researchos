'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { compile, createLatexProject, getFile, listLatexProjects, saveFile, type CompileJob, type DocFile, type LatexProject } from '@/lib/api/paper';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';
import { MonacoEditor } from '@/lib/ide/monaco';
import { Skeleton } from '@/components/ui/skeleton';

import { PaperAssistant } from './PaperAssistant';
import { PreviewPanel } from './PreviewPanel';

export function PaperWorkspace({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const projects = useQuery<LatexProject[], ApiError>({ queryKey: ['latex-projects', projectId], queryFn: () => listLatexProjects(projectId) });
  const lp = projects.data?.[0]; const lid = lp?.id;
  const create = useMutation<LatexProject, ApiError, void>({ mutationFn: () => createLatexProject(projectId, 'Paper'), onSuccess: () => qc.invalidateQueries({ queryKey: ['latex-projects', projectId] }) });
  const file = useQuery<DocFile, ApiError>({ queryKey: ['doc', projectId, lid, 'main.tex'], queryFn: () => getFile(projectId, lid as string, 'main.tex'), enabled: Boolean(lid) });
  const [content, setContent] = useState(''); useEffect(() => { if (file.data) setContent(file.data.content); }, [file.data]);
  const [saved, setSaved] = useState(false);
  const save = useMutation({ mutationFn: () => saveFile(projectId, lid as string, 'main.tex', content), onSuccess: () => { setSaved(true); setTimeout(() => setSaved(false), 2000); } });
  const [job, setJob] = useState<CompileJob | null>(null);
  const runCompile = useMutation({ mutationFn: () => compile(projectId, lid as string), onSuccess: (d) => setJob(d) });

  if (projects.isLoading) return <div className="p-6"><Skeleton className="h-64"/></div>;
  if (!lp) return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col items-center justify-center gap-4">
      <span className="text-4xl">📝</span>
      <p className="text-sm text-neutral-500">{t('paper.empty')}</p>
      <button onClick={() => create.mutate()} disabled={create.isPending} className="rounded-xl bg-neutral-900 px-6 py-2.5 text-sm font-medium text-white hover:bg-neutral-800">{create.isPending ? '…' : t('paper.newPaper')}</button>
    </div>
  );

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] min-h-0">
      <aside className="flex w-72 shrink-0 flex-col border-r border-neutral-200 bg-white"><PaperAssistant projectId={projectId} /></aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-neutral-200 bg-white px-4 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-neutral-400">{t('paper.editor')}</span>
          <span className="text-xs text-neutral-300">main.tex</span>
          <div className="ml-auto flex gap-2">
            {saved && <span className="text-xs text-emerald-600">{t('paper.saved')}</span>}
            <button onClick={() => save.mutate()} disabled={save.isPending} className="rounded-lg border border-neutral-300 bg-white px-3 py-1.5 text-[11px] font-medium text-neutral-700 hover:bg-neutral-50">{t('common.save')}</button>
            <button onClick={() => runCompile.mutate()} disabled={runCompile.isPending} className="rounded-lg bg-neutral-900 px-3 py-1.5 text-[11px] font-medium text-white hover:bg-neutral-800">{runCompile.isPending ? t('paper.compiling') : t('paper.compile')}</button>
          </div>
        </div>
        <div className="relative min-h-0 flex-1">
          {file.isLoading && <div className="flex h-full items-center justify-center text-sm text-neutral-400">{t('common.loading')}</div>}
          {file.data && <MonacoEditor height="100%" language="plaintext" value={content} onChange={(v?: string) => setContent(v ?? '')} options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: 'on' }} />}
        </div>
      </div>
      <aside className="flex w-96 shrink-0 flex-col border-l border-neutral-200 bg-white"><PreviewPanel job={job} isCompiling={runCompile.isPending} /></aside>
    </div>
  );
}
