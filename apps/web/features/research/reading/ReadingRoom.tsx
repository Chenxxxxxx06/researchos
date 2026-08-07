'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ExternalLink, FileText, NotebookPen, Sparkles, Trash2 } from 'lucide-react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { useState } from 'react';

import { ApiError } from '@/lib/api/client';
import { createReadingNote, deleteReadingNote, listReadingNotes } from '@/lib/api/knowledge';
import {
  citationKey,
  getPaper,
  getPaperSections,
  reingestPaper,
  type Paper,
  type PaperSection,
  type SectionsResponse,
} from '@/lib/api/papers';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';

import { useChatSeedStore } from '../chatSeed';
import { IngestionStatusChip } from '../search/IngestionStatusChip';
import { SectionCard } from './SectionCard';
import { SectionOutline } from './SectionOutline';

function authorsLine(authors: string[]): string {
  if (authors.length === 0) return '';
  const head = authors.slice(0, 6).join(', ');
  return authors.length > 6 ? `${head} +${authors.length - 6}` : head;
}

function shortDate(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : d.toISOString().slice(0, 10);
}

/**
 * In-app paper detail with sectioned full text (D5). Consumes the real sections
 * vocabulary (`pending|running|succeeded|abstract_only|failed`), converges via a
 * 4s poll while ingesting, and hands "Explain this / Explain paper" off to the
 * research chat by setting the chat seed and navigating back to `/research`.
 */
export function ReadingRoom({ projectId, paperId }: { projectId: string; paperId: string }) {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const missionId = searchParams.get('mission');
  const queryClient = useQueryClient();
  const setSeed = useChatSeedStore((s) => s.setSeed);

  const paper = useQuery<Paper, ApiError>({
    queryKey: ['paper', projectId, paperId],
    queryFn: () => getPaper(projectId, paperId),
    retry: false,
  });

  const sections = useQuery<SectionsResponse, ApiError>({
    queryKey: ['paper-sections', projectId, paperId],
    queryFn: () => getPaperSections(projectId, paperId),
    retry: false,
    refetchInterval: (q) => {
      const s = q.state.data?.ingest_status;
      return s === 'pending' || s === 'running' ? 4000 : false;
    },
  });

  const retry = useMutation({
    mutationFn: () => reingestPaper(projectId, paperId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['paper-sections', projectId, paperId] });
      queryClient.invalidateQueries({ queryKey: ['paper', projectId, paperId] });
    },
  });

  const backHref = `/projects/${projectId}/research`;

  if (paper.isLoading) {
    return (
      <div className="mx-auto max-w-4xl space-y-4 p-6">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (paper.isError || !paper.data) {
    const notFound = paper.error?.status === 404;
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Link href={backHref} className="mb-4 inline-flex items-center gap-1 text-xs text-muted hover:text-text">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          {t('research.reading.back')}
        </Link>
        <EmptyState
          title={notFound ? t('research.reading.notFound') : t('research.reading.failed')}
          actions={
            !notFound && (
              <Button size="sm" variant="secondary" onClick={() => paper.refetch()}>
                {t('research.common.retry')}
              </Button>
            )
          }
        />
      </div>
    );
  }

  const p = paper.data;
  const status = sections.data?.ingest_status ?? p.ingest_status;
  const key = citationKey(p.source, p.external_id);
  const date = shortDate(p.published_at);

  const explainPaper = () => {
    setSeed({ kind: 'paper', paperId: p.id, paperTitle: p.title, citationKey: key });
    router.push(backHref);
  };
  const extractInnovation = () => {
    setSeed({ kind: 'innovation', paperId: p.id, paperTitle: p.title, citationKey: key });
    router.push(backHref);
  };
  const explainSection = (section: PaperSection) => {
    setSeed({
      kind: 'section',
      paperId: p.id,
      paperTitle: p.title,
      citationKey: key,
      sectionSeq: section.seq,
      sectionHeading: section.heading,
    });
    router.push(backHref);
  };

  // Abstract-only papers still get a single readable/explainable section.
  const abstractSection: PaperSection = {
    seq: 0,
    level: 1,
    kind: 'abstract',
    heading: t('research.reading.abstract'),
    body: p.abstract ?? '',
    char_count: (p.abstract ?? '').length,
  };
  const stream: PaperSection[] =
    status === 'abstract_only' ? [abstractSection] : (sections.data?.sections ?? []);

  return (
    <div className="mx-auto max-w-[1480px] p-6">
      {/* Header */}
      <header className="mb-6 border-b border-border pb-4">
        <Link href={backHref} className="mb-3 inline-flex items-center gap-1 text-xs text-muted hover:text-text">
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />
          {t('research.reading.back')}
        </Link>
        <div className="flex items-start justify-between gap-3">
          <h1 className="text-xl font-semibold leading-tight text-text">{p.title}</h1>
          <div className="flex shrink-0 gap-2">
            <Button size="sm" variant="secondary" onClick={explainPaper}>
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              {t('research.reading.explainPaper')}
            </Button>
            <Button size="sm" onClick={extractInnovation}>
              <Sparkles className="h-3.5 w-3.5" aria-hidden="true" />
              {t('research.reading.extractInnovation')}
            </Button>
          </div>
        </div>
        {(p.authors_json.length > 0 || p.venue || date) && (
          <p className="mt-1.5 text-sm text-muted">
            {[authorsLine(p.authors_json), p.venue, date].filter(Boolean).join(' · ')}
          </p>
        )}
        <div className="mt-2.5 flex flex-wrap items-center gap-2">
          <IngestionStatusChip status={status} />
          {p.url && (
            <a
              href={p.url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"
            >
              {p.source === 'arxiv' ? 'arXiv' : p.source} <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </a>
          )}
          {p.pdf_url && (
            <a
              href={p.pdf_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 text-xs text-muted hover:text-text"
            >
              <FileText className="h-3 w-3" aria-hidden="true" /> {t('research.reading.pdf')}
            </a>
          )}
        </div>
      </header>

      {/* Body */}
      {status === 'failed' ? (
        <div className="rounded-lg bg-danger-bg px-4 py-3 text-sm text-danger">
          <p>{sections.data?.ingest_error || t('research.reading.failedNote')}</p>
          <Button size="sm" variant="secondary" className="mt-2" loading={retry.isPending} onClick={() => retry.mutate()}>
            {t('research.ingest.retry')}
          </Button>
        </div>
      ) : status === 'pending' || status === 'running' ? (
        <div className="space-y-4">
          <p className="rounded-md bg-warn-bg px-3 py-2 text-xs text-warn">{t('research.reading.pendingBody')}</p>
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-6 w-1/4" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : stream.length === 0 ? (
        <EmptyState title={t('research.reading.noSections')} className="border-none" />
      ) : (
        <div className="flex gap-6">
          <SectionOutline sections={stream} />
          <div className="min-w-0 flex-1 space-y-5">
            {status === 'abstract_only' && (
              <p className="rounded-md bg-surface-2 px-3 py-2 text-xs text-muted">
                {t('research.reading.abstractOnlyNote')}
              </p>
            )}
            {stream.map((s) => (
              <SectionWithNote
                key={s.seq}
                section={s}
                projectId={projectId}
                paperId={paperId}
                missionId={missionId}
                onExplain={() => explainSection(s)}
              />
            ))}
          </div>
          <ReadingNotesPanel projectId={projectId} paperId={paperId} missionId={missionId} />
        </div>
      )}
    </div>
  );
}

function SectionWithNote({
  section,
  projectId,
  paperId,
  missionId,
  onExplain,
}: {
  section: PaperSection;
  projectId: string;
  paperId: string;
  missionId: string | null;
  onExplain: () => void;
}) {
  const [draft, setDraft] = useState(false);
  return (
    <div>
      <SectionCard section={section} onExplain={onExplain} onNote={() => setDraft(true)} />
      {draft && (
        <InlineNoteComposer
          projectId={projectId}
          paperId={paperId}
          missionId={missionId}
          section={section}
          onClose={() => setDraft(false)}
        />
      )}
    </div>
  );
}

function InlineNoteComposer({
  projectId,
  paperId,
  missionId,
  section,
  onClose,
}: {
  projectId: string;
  paperId: string;
  missionId: string | null;
  section: PaperSection;
  onClose: () => void;
}) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const queryClient = useQueryClient();
  const [quote, setQuote] = useState('');
  const [content, setContent] = useState('');
  const [tags, setTags] = useState('');
  const save = useMutation({
    mutationFn: () => createReadingNote(projectId, paperId, {
      mission_id: missionId,
      section_id: section.id ?? null,
      quote,
      content,
      tags: tags.split(/[,，]/).map((item) => item.trim()).filter(Boolean),
    }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['reading-notes', projectId, paperId, missionId] });
      toast({ title: zh ? '笔记已保存并绑定原文位置' : 'Note saved with its source section' });
      onClose();
    },
    onError: (error) => toast({ title: zh ? '笔记保存失败' : 'Could not save note', description: error instanceof Error ? error.message : undefined, variant: 'error' }),
  });
  return (
    <div className="-mt-2 mb-5 border-l-2 border-info bg-info-bg/45 p-4">
      <div className="mb-3 flex items-center justify-between"><p className="text-xs font-semibold text-text">{zh ? `记录到「${section.heading}」` : `Note on “${section.heading}”`}</p><button type="button" onClick={onClose} className="text-[11px] text-muted hover:text-text">{zh ? '取消' : 'Cancel'}</button></div>
      <textarea value={quote} onChange={(event) => setQuote(event.target.value)} rows={2} className="w-full resize-y rounded-md border border-border-strong bg-bg p-2.5 text-xs leading-5 text-muted outline-none focus:ring-2 focus:ring-focus/60" placeholder={zh ? '粘贴需要保留的原文引句（可选）' : 'Paste the exact source quote (optional)'} />
      <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={3} className="mt-2 w-full resize-y rounded-md border border-border-strong bg-bg p-2.5 text-sm leading-6 text-text outline-none focus:ring-2 focus:ring-focus/60" placeholder={zh ? '写下理解、疑问或与其他论文的联系' : 'Write an interpretation, question, or connection'} />
      <div className="mt-2 flex gap-2"><input value={tags} onChange={(event) => setTags(event.target.value)} className="h-8 min-w-0 flex-1 rounded-md border border-border-strong bg-bg px-2.5 text-xs text-text outline-none focus:ring-2 focus:ring-focus/60" placeholder={zh ? '标签，用逗号分隔' : 'Tags, comma separated'} /><Button size="sm" onClick={() => save.mutate()} loading={save.isPending} disabled={!content.trim()}>{zh ? '保存笔记' : 'Save note'}</Button></div>
    </div>
  );
}

function ReadingNotesPanel({ projectId, paperId, missionId }: { projectId: string; paperId: string; missionId: string | null }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const queryClient = useQueryClient();
  const notes = useQuery({ queryKey: ['reading-notes', projectId, paperId, missionId], queryFn: () => listReadingNotes(projectId, paperId, missionId) });
  const remove = useMutation({
    mutationFn: (noteId: string) => deleteReadingNote(projectId, noteId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['reading-notes', projectId, paperId, missionId] }),
  });
  return (
    <aside className="sticky top-4 hidden h-fit w-72 shrink-0 border-l border-border pl-5 xl:block">
      <div className="flex items-center justify-between"><h2 className="flex items-center gap-2 text-xs font-semibold text-text"><NotebookPen className="h-3.5 w-3.5 text-info" />{zh ? '页内笔记' : 'Reading notes'}</h2><span className="font-mono text-[10px] text-faint">{notes.data?.length ?? 0}</span></div>
      {missionId && <p className="mt-2 border-l-2 border-info/35 pl-2 text-[10px] leading-4 text-muted">{zh ? '当前只显示本研究任务的笔记。' : 'Filtered to this research mission.'}</p>}
      <div className="mt-4 max-h-[calc(100dvh-10rem)] space-y-3 overflow-y-auto pr-1">
        {(notes.data ?? []).map((note) => (
          <article key={note.id} className="group bg-surface-2 p-3">
            {note.quote && <p className="line-clamp-3 border-l border-border-strong pl-2 text-[10px] italic leading-4 text-faint">“{note.quote}”</p>}
            <p className="mt-2 whitespace-pre-wrap text-xs leading-5 text-text">{note.content}</p>
            <div className="mt-2 flex items-center justify-between gap-2"><p className="truncate text-[9px] text-faint">{note.tags_json.join(' · ')} · {new Date(note.updated_at).toLocaleDateString()}</p><button type="button" onClick={() => remove.mutate(note.id)} className="opacity-0 transition-opacity group-hover:opacity-100"><Trash2 className="h-3 w-3 text-danger" /></button></div>
          </article>
        ))}
        {!notes.isLoading && (notes.data?.length ?? 0) === 0 && <p className="py-5 text-xs leading-5 text-muted">{zh ? '将鼠标移到任意章节标题，点击“笔记”即可在原文位置记录。' : 'Hover a section heading and choose Note to capture grounded reading notes.'}</p>}
      </div>
    </aside>
  );
}
