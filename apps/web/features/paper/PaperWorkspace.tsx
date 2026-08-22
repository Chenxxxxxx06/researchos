'use client';

/**
 * Overleaf-grade paper workspace (partition: frontend-paper, Design A).
 *
 * Layout: docked AssistantDock (left) · themed Monaco editor with a floating
 * SelectionToolbar + TrackedChanges overlay (center) · tabbed right rail
 * (Preview / Anchors / Figures / Cite). Saves are compare-and-swap against the
 * document version; a 409 `document_version_conflict` opens the MergeDialog.
 * Selection edits fire a server-side selection-op whose resulting suggestion is
 * rendered inline for accept/reject. `monaco-editor` is TYPES ONLY.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Monaco, OnMount } from '@monaco-editor/react';
import type { editor } from 'monaco-editor';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { BookOpen, FileText, Newspaper, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, ScrollText, ShieldCheck, Zap } from 'lucide-react';
import Link from 'next/link';

import { ApiError } from '@/lib/api/client';
import {
  acceptSuggestion,
  createLatexProject,
  createSelectionOp,
  getFile,
  isVersionConflict,
  listLatexProjects,
  listSuggestions,
  rejectSuggestion,
  saveFile,
  type DocRange,
  type PaperTemplateId,
  type Suggestion,
  type SuggestionOp,
} from '@/lib/api/documents';
import { EvidenceStamp } from '@/components/provenance/EvidenceStamp';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from '@/components/ui/toast';
import { useI18n } from '@/lib/i18n';
import { ThemedMonacoEditor } from '@/lib/ide/monaco';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';

import { AnchorsPanel } from './AnchorsPanel';
import { AssistantDock } from './AssistantDock';
import { CitePicker } from './CitePicker';
import { FiguresPanel } from './FiguresPanel';
import { MergeDialog, type MergeDialogState } from './MergeDialog';
import { PreviewPanel } from './PreviewPanel';
import { SelectionToolbar } from './SelectionToolbar';
import { TrackedChanges } from './TrackedChanges';
import { clearDraft, readDraft, writeConflictBackup, writeDraft } from './draft';
import { useCompileJob } from './useCompileJob';
import { useSuggestionStore } from './suggestionStore';

const MAIN = 'main.tex';
type RailTab = 'preview' | 'anchors' | 'figures' | 'cite';

export function PaperWorkspace({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const qc = useQueryClient();

  const projects = useQuery<Awaited<ReturnType<typeof listLatexProjects>>, ApiError>({
    queryKey: ['latex-projects', projectId],
    queryFn: () => listLatexProjects(projectId),
  });
  const lp = projects.data?.[0];
  const lid = lp?.id;

  const create = useMutation({
    mutationFn: (templateId: PaperTemplateId) =>
      createLatexProject(projectId, 'Paper', templateId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['latex-projects', projectId] }),
  });

  const file = useQuery({
    queryKey: ['doc', projectId, lid, MAIN],
    queryFn: () => getFile(projectId, lid as string, MAIN),
    enabled: Boolean(lid),
  });

  // --- editor + buffer state ------------------------------------------------
  const [content, setContent] = useState('');
  const [savedContent, setSavedContent] = useState('');
  const [version, setVersion] = useState<number | null>(null);
  const [rail, setRail] = useState<RailTab>('preview');
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [railOpen, setRailOpen] = useState(true);
  const [autoCompile, setAutoCompile] = useState(true);
  const [merge, setMerge] = useState<MergeDialogState | null>(null);
  const [draftPrompt, setDraftPrompt] = useState<string | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const loadedLidRef = useRef<string | null>(null);
  const initialCompileLidRef = useRef<string | null>(null);
  const compileAfterSaveRef = useRef(false);
  const contentRef = useRef('');
  const [ed, setEd] = useState<editor.IStandaloneCodeEditor | null>(null);
  const [monaco, setMonaco] = useState<Monaco | null>(null);

  const dirty = content !== savedContent;
  const suggestions = useSuggestionStore((s) => s.items);
  const hydrateSuggestions = useSuggestionStore((s) => s.hydrate);
  const dismissSuggestion = useSuggestionStore((s) => s.dismiss);
  const clearSuggestions = useSuggestionStore((s) => s.clear);
  const { job, isCompiling, compile } = useCompileJob(projectId, lid);
  const { runs, trackRun } = useProjectAgentEvents(projectId);
  const [opRunId, setOpRunId] = useState<string | null>(null);

  useEffect(() => {
    contentRef.current = content;
  }, [content]);

  // Initialize the buffer only on the FIRST load of a document. Subsequent
  // refetches (our own save invalidates the query) must NOT overwrite the live
  // buffer, or edits made while a save is in flight are lost. save.onSuccess
  // already advances savedContent/version; an external change surfaces via the
  // CAS 409 → MergeDialog, never a silent clobber.
  useEffect(() => {
    if (!file.data || !lid || loadedLidRef.current === lid) return;
    loadedLidRef.current = lid;
    setSavedContent(file.data.content);
    setVersion(file.data.version);
    setContent(file.data.content);
    const draft = readDraft(lid, MAIN);
    setDraftPrompt(draft && draft.content !== file.data.content ? draft.content : null);
    clearSuggestions();
  }, [file.data, lid, clearSuggestions]);

  // Persist a local draft as the buffer diverges (autosave-safety).
  useEffect(() => {
    if (!lid || version === null || !dirty) return;
    const h = setTimeout(
      () => writeDraft(lid, MAIN, { content, baseVersion: version, savedAt: Date.now() }),
      600,
    );
    return () => clearTimeout(h);
  }, [content, dirty, lid, version]);

  const refetchSuggestions = useCallback(async () => {
    if (!lid) return;
    try {
      const page = await listSuggestions(projectId, lid, { status: 'proposed', path: MAIN });
      hydrateSuggestions(page.items);
    } catch {
      /* 404 before the endpoint lands → no suggestions, non-fatal */
    }
  }, [projectId, lid, hydrateSuggestions]);

  // When a selection-op run completes, pull its suggestion into the overlay.
  useEffect(() => {
    if (!opRunId) return;
    const run = runs[opRunId];
    if (run && (run.status === 'completed' || run.status === 'failed')) {
      if (run.status === 'completed') void refetchSuggestions();
      else toast({ title: t('paper.ai.failed'), variant: 'error' });
      setOpRunId(null);
    }
  }, [opRunId, runs, refetchSuggestions, t]);

  // --- save (compare-and-swap) ----------------------------------------------
  const save = useMutation<
    Awaited<ReturnType<typeof saveFile>>,
    ApiError,
    { text: string; expected: number | null }
  >({
    mutationFn: ({ text, expected }) =>
      saveFile(projectId, lid as string, { path: MAIN, content: text, expected_version: expected }),
    onSuccess: (doc, variables) => {
      setSavedContent(doc.content);
      setVersion(doc.version);
      if (lid) clearDraft(lid, MAIN);
      qc.invalidateQueries({ queryKey: ['doc', projectId, lid, MAIN] });
      const shouldCompile = compileAfterSaveRef.current || autoCompile;
      compileAfterSaveRef.current = false;
      if (shouldCompile && variables.text === contentRef.current) void compile();
    },
    onError: async (err) => {
      if (isVersionConflict(err) && lid) {
        try {
          const server = await getFile(projectId, lid, MAIN);
          setMerge({
            server: server.content,
            serverVersion: server.version,
            mine: content,
            mineVersion: version ?? 0,
          });
        } catch {
          toast({ title: t('paper.saveFailed'), variant: 'error' });
        }
      } else {
        toast({ title: t('paper.saveFailed'), variant: 'error' });
      }
    },
  });

  const doSave = useCallback(() => {
    if (!lid || save.isPending) return;
    save.mutate({ text: content, expected: version });
  }, [lid, content, version, save]);

  const requestCompile = useCallback(() => {
    if (dirty) {
      compileAfterSaveRef.current = true;
      doSave();
      return;
    }
    void compile();
  }, [compile, dirty, doSave]);

  // Debounced server autosave keeps the compiled PDF aligned with the editor
  // without issuing a request for every keystroke.
  useEffect(() => {
    if (!autoCompile || !dirty || save.isPending || version === null) return;
    const timer = window.setTimeout(doSave, 900);
    return () => window.clearTimeout(timer);
  }, [autoCompile, dirty, doSave, save.isPending, version]);

  // Compile once when a paper is opened so the preview is never an unexplained
  // blank panel. Identical source snapshots reuse the backend PDF cache.
  useEffect(() => {
    if (!autoCompile || !lid || !file.data || initialCompileLidRef.current === lid) return;
    initialCompileLidRef.current = lid;
    void compile();
  }, [autoCompile, compile, file.data, lid]);

  // Ctrl/Cmd+S to save.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        if (dirty) doSave();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [dirty, doSave]);

  // Warn before discarding unsaved edits.
  useEffect(() => {
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', onBeforeUnload);
    return () => window.removeEventListener('beforeunload', onBeforeUnload);
  }, [dirty]);

  // --- editor helpers -------------------------------------------------------
  const onMount = useCallback<OnMount>((editorInstance, monacoInstance) => {
    editorRef.current = editorInstance;
    setEd(editorInstance);
    setMonaco(monacoInstance as Monaco);
  }, []);

  const insertAtCursor = useCallback((text: string) => {
    const editor = editorRef.current;
    if (!editor) return;
    const selection = editor.getSelection();
    if (!selection) return;
    editor.executeEdits('ros-insert', [{ range: selection, text, forceMoveMarkers: true }]);
    editor.focus();
  }, []);

  const jumpToLine = useCallback((line: number) => {
    const editor = editorRef.current;
    if (!editor || line < 1) return;
    editor.revealLineInCenter(line);
    editor.setPosition({ lineNumber: line, column: 1 });
    editor.focus();
  }, []);

  // --- selection-op → suggestion --------------------------------------------
  const runSelectionOp = useCallback(
    (op: SuggestionOp, range: DocRange, selectionText: string, instruction?: string) => {
      if (!lid) return;
      if (dirty) {
        toast({ title: t('paper.tracked.saveFirst'), variant: 'warning' });
        return;
      }
      createSelectionOp(projectId, lid, {
        op,
        path: MAIN,
        range,
        selection_text: selectionText,
        expected_version: version,
        instruction,
      })
        .then((res) => {
          trackRun(res.agent_run_id);
          setOpRunId(res.agent_run_id);
        })
        .catch(() => toast({ title: t('paper.ai.failed'), variant: 'error' }));
    },
    [projectId, lid, version, dirty, trackRun, t],
  );

  const applyAccepted = useCallback(
    (updated: { content: string; version: number }) => {
      setContent(updated.content);
      setSavedContent(updated.content);
      setVersion(updated.version);
    },
    [],
  );

  const acceptOne = useMutation<
    Awaited<ReturnType<typeof acceptSuggestion>>,
    ApiError,
    Suggestion
  >({
    mutationFn: (s) => acceptSuggestion(projectId, lid as string, s.id, version),
    onSuccess: (res, s) => {
      dismissSuggestion(s.id);
      applyAccepted({ content: res.file.content, version: res.file.version });
      toast({ title: t('paper.tracked.applied'), variant: 'success' });
    },
    onError: () => toast({ title: t('paper.tracked.conflict'), variant: 'error' }),
  });

  const rejectOne = useMutation<Suggestion, ApiError, Suggestion>({
    mutationFn: (s) => rejectSuggestion(projectId, lid as string, s.id),
    onSuccess: (_res, s) => dismissSuggestion(s.id),
  });

  const revealSuggestion = useCallback((s: Suggestion) => jumpToLine(s.range.start.line), [jumpToLine]);

  // --- merge resolution -----------------------------------------------------
  const keepMine = useCallback(() => {
    if (!merge) return;
    save.mutate({ text: merge.mine, expected: merge.serverVersion });
    setMerge(null);
  }, [merge, save]);

  const takeServer = useCallback(() => {
    if (!merge || !lid) return;
    writeConflictBackup(lid, MAIN, merge.mine);
    setContent(merge.server);
    setSavedContent(merge.server);
    setVersion(merge.serverVersion);
    clearDraft(lid, MAIN);
    setMerge(null);
  }, [merge, lid]);

  const railTabs: { key: RailTab; label: string }[] = useMemo(
    () => [
      { key: 'preview', label: t('paper.preview') },
      { key: 'anchors', label: t('paper.anchors.tab') },
      { key: 'figures', label: t('paper.figures.tab') },
      { key: 'cite', label: t('paper.cite.tab') },
    ],
    [t],
  );

  // --- render ---------------------------------------------------------------
  if (projects.isLoading) {
    return (
      <div className="p-6">
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }
  if (!lp) {
    const templates: {
      id: PaperTemplateId;
      icon: typeof FileText;
      title: string;
      description: string;
    }[] = [
      {
        id: 'article',
        icon: FileText,
        title: t('paper.template.article'),
        description: t('paper.template.articleDescription'),
      },
      {
        id: 'ieee',
        icon: ScrollText,
        title: 'IEEE',
        description: t('paper.template.ieeeDescription'),
      },
      {
        id: 'acm',
        icon: BookOpen,
        title: 'ACM',
        description: t('paper.template.acmDescription'),
      },
      {
        id: 'elsevier',
        icon: Newspaper,
        title: 'Elsevier',
        description: t('paper.template.elsevierDescription'),
      },
      { id: 'neurips', icon: ScrollText, title: 'NeurIPS', description: 'Offline starter with evidence, ablation, and limitation sections.' },
      { id: 'icml', icon: ScrollText, title: 'ICML', description: 'Offline starter for methods, theory, experiments, and ablations.' },
      { id: 'iclr', icon: ScrollText, title: 'ICLR', description: 'Offline starter with analysis and reproducibility sections.' },
      { id: 'cvpr', icon: ScrollText, title: 'CVPR', description: 'Offline vision-paper starter with qualitative and ablation sections.' },
      { id: 'acl', icon: ScrollText, title: 'ACL', description: 'Offline NLP starter with limitations and ethics sections.' },
      { id: 'aaai', icon: ScrollText, title: 'AAAI', description: 'Offline AI starter for experiments and discussion.' },
    ];
    return (
      <div className="mx-auto flex min-h-[calc(100dvh-8rem)] max-w-5xl flex-col justify-center p-6">
        <div className="mb-8 max-w-2xl">
          <p className="text-xs font-medium text-accent">{t('paper.title')}</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.04em] text-text">{t('paper.empty')}</h1>
          <p className="mt-3 text-sm leading-6 text-muted">{t('paper.template.choose')}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {templates.map((template) => {
            const Icon = template.icon;
            return (
              <button
                key={template.id}
                type="button"
                className="group rounded-lg border border-border bg-surface p-5 text-left shadow-elev1 transition hover:-translate-y-0.5 hover:border-accent/50 hover:shadow-elev2 disabled:opacity-50"
                disabled={create.isPending}
                onClick={() => create.mutate(template.id)}
              >
                <Icon className="mb-6 size-6 text-accent" />
                <div className="font-semibold text-text">{template.title}</div>
                <p className="mt-2 text-xs leading-5 text-muted">
                  {template.description}
                </p>
              </button>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <div className="-m-5 flex h-[calc(100dvh-4rem)] min-h-0 lg:-m-6 xl:-m-8">
      {assistantOpen && (
        <aside className="hidden w-64 shrink-0 flex-col border-r border-border bg-surface xl:flex">
          <AssistantDock projectId={projectId} latexProjectId={lid as string} onInsert={insertAtCursor} />
        </aside>
      )}

      <div className="relative flex min-w-0 flex-1 flex-col">
        <div className="workspace-toolbar flex min-h-12 items-center gap-2 px-3 py-2 sm:px-4">
          <Button size="icon" variant="ghost" onClick={() => setAssistantOpen((value) => !value)} title={t('paper.assistant')}>
            {assistantOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </Button>
          <span className="text-xs font-semibold text-text">{t('paper.editor')}</span>
          <span className="font-mono text-[11px] text-faint">{MAIN}</span>
          {file.data && (
            <EvidenceStamp
              status={dirty ? 'unsaved' : 'saved'}
              tone={dirty ? 'warn' : 'success'}
              id={`v${file.data.version}`}
              date={new Date(file.data.updated_at).toLocaleDateString()}
              className="hidden lg:inline-flex"
            />
          )}
          <div className="ml-auto flex items-center gap-1.5">
            <span className="text-[11px] text-muted">
              {dirty
                ? t('paper.unsaved')
                : version !== null
                  ? t('paper.savedVersion', { version })
                  : ''}
            </span>
            <button
              type="button"
              aria-pressed={autoCompile}
              onClick={() => setAutoCompile((value) => !value)}
              className={`hidden h-8 items-center gap-1.5 rounded-md border px-2.5 text-[11px] font-medium lg:inline-flex ${
                autoCompile
                  ? 'border-success/30 bg-success-bg text-success'
                  : 'border-border text-muted hover:bg-surface-2'
              }`}
              title="编辑停止 0.9 秒后自动保存并编译 PDF"
            >
              <Zap className="h-3.5 w-3.5" />实时 PDF
            </button>
            <Button size="sm" variant="ghost" onClick={doSave} disabled={!dirty} loading={save.isPending}>
              {t('common.save')}
            </Button>
            <Link href={`/projects/${projectId}/reviewer`} className="hidden h-8 items-center gap-1.5 rounded-md border border-border px-2.5 text-xs font-medium text-muted hover:bg-surface-2 hover:text-text sm:inline-flex">
              <ShieldCheck className="h-3.5 w-3.5" />{t('nav.reviewer')}
            </Link>
            <Button
              size="sm"
              onClick={requestCompile}
              loading={isCompiling || (save.isPending && compileAfterSaveRef.current)}
              disabled={save.isPending && dirty}
            >
              {isCompiling ? t('paper.compiling') : t('paper.compile')}
            </Button>
            <Button size="icon" variant="ghost" onClick={() => setRailOpen((value) => !value)} title={t('paper.preview')}>
              {railOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
            </Button>
          </div>
        </div>

        {draftPrompt !== null && (
          <div className="flex items-center gap-3 border-b border-warn/40 bg-warn/10 px-4 py-1.5 text-xs text-text">
            <span>{t('paper.draftFound')}</span>
            <button
              type="button"
              className="font-medium text-accent hover:underline"
              onClick={() => {
                setContent(draftPrompt);
                setDraftPrompt(null);
              }}
            >
              {t('paper.restore')}
            </button>
            <button
              type="button"
              className="text-muted hover:underline"
              onClick={() => {
                if (lid) clearDraft(lid, MAIN);
                setDraftPrompt(null);
              }}
            >
              {t('paper.discard')}
            </button>
          </div>
        )}

        <div className="relative min-h-0 flex-1">
          {file.isLoading && (
            <div className="flex h-full items-center justify-center text-sm text-muted">
              {t('common.loading')}
            </div>
          )}
          {file.data && (
            <ThemedMonacoEditor
              height="100%"
              language="latex"
              value={content}
              onChange={(v?: string) => setContent(v ?? '')}
              onMount={onMount}
              options={{ wordWrap: 'on', fontSize: 13, minimap: { enabled: false } }}
            />
          )}
          {ed && monaco && (
            <SelectionToolbar editor={ed} monaco={monaco} onAction={runSelectionOp} disabled={dirty} />
          )}
          {ed && !dirty && suggestions.length > 0 && (
            // Only overlay decorations on the clean, saved buffer they were
            // computed against — while dirty the ranges would drift and accept
            // is blocked anyway, so the tray stays hidden until the next save.
            <TrackedChanges
              editor={ed}
              suggestions={suggestions}
              pendingId={acceptOne.isPending ? acceptOne.variables?.id : null}
              onAccept={(s) => {
                // Accepting replaces the buffer with the server's post-accept
                // content; block it while there are unsaved edits to apply-first.
                if (dirty) {
                  toast({ title: t('paper.tracked.saveFirst'), variant: 'warning' });
                  return;
                }
                acceptOne.mutate(s);
              }}
              onReject={(s) => rejectOne.mutate(s)}
              onReveal={revealSuggestion}
            />
          )}
        </div>
      </div>

      {railOpen && (
      <aside className="hidden w-[22rem] shrink-0 flex-col border-l border-border bg-surface xl:flex 2xl:w-[26rem]">
        <Tabs value={rail} onValueChange={(v) => setRail(v as RailTab)}>
          <TabsList className="px-3">
            {railTabs.map((tab) => (
              <TabsTrigger key={tab.key} value={tab.key}>
                {tab.label}
              </TabsTrigger>
            ))}
          </TabsList>
          <TabsContent value="preview" className="min-h-0 flex-1">
            <PreviewPanel job={job} isCompiling={isCompiling} onJumpToLine={jumpToLine} />
          </TabsContent>
          <TabsContent value="anchors" className="min-h-0 flex-1 overflow-y-auto">
            <AnchorsPanel projectId={projectId} onInsert={insertAtCursor} />
          </TabsContent>
          <TabsContent value="figures" className="min-h-0 flex-1 overflow-y-auto">
            <FiguresPanel projectId={projectId} latexProjectId={lid as string} onInsert={insertAtCursor} />
          </TabsContent>
          <TabsContent value="cite" className="min-h-0 flex-1 overflow-y-auto">
            <CitePicker projectId={projectId} latexProjectId={lid as string} onInsert={insertAtCursor} />
          </TabsContent>
        </Tabs>
      </aside>
      )}

      <MergeDialog
        state={merge}
        busy={save.isPending}
        onKeepMine={keepMine}
        onTakeServer={takeServer}
        onCancel={() => setMerge(null)}
      />
    </div>
  );
}
