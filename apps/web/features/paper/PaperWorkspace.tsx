'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';

import { useI18n } from '@/lib/i18n';
import { ApiError } from '@/lib/api/client';
import {
  compile,
  createLatexProject,
  getFile,
  listLatexProjects,
  saveFile,
  type CompileJob,
  type DocFile,
  type LatexProject,
} from '@/lib/api/paper';
import { MonacoEditor } from '@/lib/ide/monaco';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';

import { PaperAssistant } from './PaperAssistant';
import { PreviewPanel } from './PreviewPanel';

const MAIN_FILE = 'main.tex';

export function PaperWorkspace({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const projects = useQuery<LatexProject[], ApiError>({
    queryKey: ['latex-projects', projectId],
    queryFn: () => listLatexProjects(projectId),
  });

  const latexProject = projects.data?.[0];
  const latexId = latexProject?.id;

  const createPaper = useMutation<LatexProject, ApiError, void>({
    mutationFn: () => createLatexProject(projectId, 'Paper'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['latex-projects', projectId] }),
  });

  const file = useQuery<DocFile, ApiError>({
    queryKey: ['doc', projectId, latexId, MAIN_FILE],
    queryFn: () => getFile(projectId, latexId as string, MAIN_FILE),
    enabled: Boolean(latexId),
  });

  const [content, setContent] = useState('');
  useEffect(() => {
    if (file.data) setContent(file.data.content);
  }, [file.data]);

  const [saved, setSaved] = useState(false);
  const save = useMutation<DocFile, ApiError, void>({
    mutationFn: () => saveFile(projectId, latexId as string, MAIN_FILE, content),
    onSuccess: () => {
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const [job, setJob] = useState<CompileJob | null>(null);
  const runCompile = useMutation<CompileJob, ApiError, void>({
    mutationFn: () => compile(projectId, latexId as string),
    onSuccess: (data) => {
      setJob(data);
      file.refetch();
    },
  });

  if (projects.isLoading) {
    return (
      <div className="-m-6 flex h-[calc(100vh-3.5rem)] flex-col gap-3 p-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="min-h-0 flex-1" />
      </div>
    );
  }

  if (projects.isError) {
    return (
      <div className="-m-6 flex h-[calc(100vh-3.5rem)] items-center justify-center">
        <p className="text-sm text-red-600">{projects.error.message || t('common.error')}</p>
      </div>
    );
  }

  if (!latexProject) {
    return (
      <div className="-m-6 flex h-[calc(100vh-3.5rem)] flex-col items-center justify-center gap-4">
        <p className="text-sm text-neutral-500">{t('paper.empty')}</p>
        <Button
          onClick={() => createPaper.mutate()}
          disabled={createPaper.isPending}
        >
          {createPaper.isPending ? t('common.loading') : t('paper.newPaper')}
        </Button>
        {createPaper.isError && (
          <p className="text-xs text-red-600">{createPaper.error.message || t('common.error')}</p>
        )}
      </div>
    );
  }

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] min-h-0">
      {/* Left: AI assistant */}
      <aside className="flex w-72 shrink-0 flex-col border-r border-neutral-200 bg-white">
        <PaperAssistant projectId={projectId} />
      </aside>

      {/* Center: editor + toolbar */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-neutral-200 bg-white px-3 py-2">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {t('paper.editor')}
          </h2>
          <div className="ml-auto flex items-center gap-2">
            {saved && <span className="text-xs text-emerald-600">{t('paper.saved')}</span>}
            <Button
              size="sm"
              variant="secondary"
              disabled={save.isPending || file.isLoading}
              onClick={() => save.mutate()}
            >
              {save.isPending ? t('common.loading') : t('common.save')}
            </Button>
            <Button
              size="sm"
              disabled={runCompile.isPending || file.isLoading}
              onClick={() => runCompile.mutate()}
            >
              {runCompile.isPending ? t('paper.compiling') : t('paper.compile')}
            </Button>
          </div>
        </div>

        <div className="relative min-h-0 flex-1">
          {file.isLoading && (
            <div className="flex h-full items-center justify-center text-sm text-neutral-400">
              {t('common.loading')}
            </div>
          )}
          {file.isError && (
            <div className="flex h-full items-center justify-center text-sm text-red-600">
              {file.error.message || t('common.error')}
            </div>
          )}
          {file.data && (
            <MonacoEditor
              height="100%"
              language="plaintext"
              value={content}
              onChange={(v?: string) => setContent(v ?? '')}
              options={{ minimap: { enabled: false }, fontSize: 13, wordWrap: 'on' }}
            />
          )}
          {(save.isError || runCompile.isError) && (
            <p className="absolute bottom-2 left-3 text-xs text-red-600">
              {(save.error ?? runCompile.error)?.message || t('common.error')}
            </p>
          )}
        </div>
      </div>

      {/* Right: preview */}
      <aside className="flex w-96 shrink-0 flex-col border-l border-neutral-200 bg-white">
        <PreviewPanel job={job} isCompiling={runCompile.isPending} />
      </aside>
    </div>
  );
}
