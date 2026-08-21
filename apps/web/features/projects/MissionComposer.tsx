'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { ArrowRight, BookOpen, Inbox, LoaderCircle, Sparkles } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { createMission } from '@/lib/api/missions';
import { useI18n } from '@/lib/i18n';

export function MissionComposer({ projectId, latestMissionId }: { projectId: string; latestMissionId?: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const router = useRouter();
  const queryClient = useQueryClient();
  const [topic, setTopic] = useState('');
  const create = useMutation({
    mutationFn: () => createMission(projectId, {
      topic: topic.trim(),
      objective: '',
      scope: { minimum_papers: 8, sources: ['arxiv', 'openalex', 'semantic_scholar'] },
    }),
    onSuccess: (mission) => {
      void queryClient.invalidateQueries({ queryKey: ['missions', projectId] });
      router.push(`/projects/${projectId}/missions/${mission.id}`);
    },
  });

  const submit = () => {
    if (topic.trim() && !create.isPending) create.mutate();
  };

  return (
    <div className="mt-7 max-w-3xl overflow-hidden rounded-lg border border-border-strong bg-overlay/95 shadow-elev2 backdrop-blur">
      <label htmlFor="mission-composer" className="sr-only">{zh ? '研究问题' : 'Research question'}</label>
      <textarea
        id="mission-composer"
        rows={2}
        value={topic}
        onChange={(event) => setTopic(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            submit();
          }
        }}
        placeholder={zh ? '描述你想研究的问题，例如：如何降低多模态模型在长尾类别上的幻觉？' : 'Describe a research question, for example: how can we reduce hallucination on long-tail classes?'}
        className="min-h-20 w-full resize-none bg-transparent px-4 pb-2 pt-4 text-sm leading-6 text-text outline-none placeholder:text-faint"
      />
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border bg-surface/75 px-2.5 py-2">
        <div className="flex items-center gap-1">
          <Link href={`/projects/${projectId}/inbox`} className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium text-muted hover:bg-surface-2 hover:text-text">
            <Inbox className="h-3.5 w-3.5" aria-hidden="true" />{zh ? '导入资料' : 'Add sources'}
          </Link>
          <Link href={`/projects/${projectId}/research?focus=search`} className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium text-muted hover:bg-surface-2 hover:text-text">
            <BookOpen className="h-3.5 w-3.5" aria-hidden="true" />{zh ? '检索文献' : 'Search papers'}
          </Link>
          {latestMissionId && (
            <Link href={`/projects/${projectId}/missions/${latestMissionId}`} className="hidden h-8 items-center rounded-md px-2.5 text-xs font-medium text-muted hover:bg-surface-2 hover:text-text sm:inline-flex">
              {zh ? '继续最近任务' : 'Continue mission'}
            </Link>
          )}
        </div>
        <button
          type="button"
          onClick={submit}
          disabled={!topic.trim() || create.isPending}
          className="group inline-flex h-9 items-center gap-2 whitespace-nowrap rounded-md border border-accent bg-accent px-3.5 text-xs font-semibold text-accent-fg shadow-elev1 transition-[transform,box-shadow,background-color] hover:-translate-y-0.5 hover:bg-accent-hover hover:shadow-elev2 active:translate-y-0 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45"
        >
          {create.isPending ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
          {zh ? '开始研究' : 'Start research'}
          <ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" />
        </button>
      </div>
      {create.error && <p role="alert" className="border-t border-danger/20 bg-danger-bg px-4 py-2 text-xs text-danger">{create.error instanceof Error ? create.error.message : (zh ? '创建任务失败' : 'Could not create mission')}</p>}
    </div>
  );
}
