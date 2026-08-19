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

import { BookOpen, FileText, Newspaper, ScrollText } from 'lucide-react';

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
import { Button } from '@/components/ui/button';
import { EvidenceStamp } from '@/components/provenance/EvidenceStamp';
import { ProvenanceTrace } from '@/components/provenance/ProvenanceTrace';
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
  const [merge, setMerge] = useState<MergeDialogState | null>(null);
  const [draftPrompt, setDraftPrompt] = useState<string | null>(null);
  const editorRef = useRef<editor.IStandaloneCodeEditor | null>(null);
  const loadedLidRef = useRef<string | null>(null);
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
    onSuccess: (doc) => {
      setSavedContent(doc.content);
      setVersion(doc.version);
      if (lid) clearDraft(lid, MAIN);
      qc.invalidateQueries({ queryKey: ['doc', projectId, lid, MAIN] });
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
    ];
    return (
      <div className="mx-auto flex min-h-[calc(100vh-7rem)] max-w-5xl flex-col justify-center p-6">
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold text-foreground">{t('paper.empty')}</h1>
          <p className="mt-2 text-sm text-muted-foreground">{t('paper.template.choose')}</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {templates.map((template) => {
            const Icon = template.icon;
            return (
              <button
                key={template.id}
                type="button"
                className="group rounded-xl border border-border bg-surface p-5 text-left transition hover:border-primary disabled:opacity-50"
                disabled={create.isPending}
                onClick={() => create.mutate(template.id)}
              >
                <Icon className="mb-4 size-7 text-primary" />
                <div className="font-medium text-foreground">{template.title}</div>
                <p className="mt-2 text-xs leading-5 text-muted-foreground">
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
    <div className="-m-6 flex h-[calc(100vh-3rem)] min-h-0">
      <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-surface">
        <AssistantDock projectId={projectId} latexProjectId={lid as string} onInsert={insertAtCursor} />
      </aside>

      <div className="relative flex min-w-0 flex-1 flex-col">
        <div className="flex items-center gap-2 border-b border-border bg-surface px-4 py-2">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted">
            {t('paper.editor')}
          </span>
          <span className="text-xs text-faint">{MAIN}</span>
          {file.data && (
            <EvidenceStamp
              status={dirty ? 'unsaved' : 'saved'}
              tone={dirty ? 'warn' : 'success'}
              id={`v${file.data.version}`}
              date={new Date(file.data.updated_at).toLocaleDateString()}
            />
          )}
          <div className="ml-auto flex items-center gap-2">
            <span className="text-[11px] text-muted">
              {dirty
                ? t('paper.unsaved')
                : version !== null
                  ? t('paper.savedVersion', { version })
                  : ''}
            </span>
            <Button size="sm" variant="ghost" onClick={doSave} disabled={!dirty} loading={save.isPending}>
              {t('common.save')}
            </Button>
            <Button size="sm" onClick={() => compile()} loading={isCompiling}>
              {isCompiling ? t('paper.compiling') : t('paper.compile')}
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

      <aside className="flex w-96 shrink-0 flex-col border-l border-border bg-surface">
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
