'use client';

/**
 * Editor pane (D6). Buffer/dirty model via the owned store: a buffer exists iff
 * it differs from the server content it forked from, so typing back to the
 * original un-dirties. Closing a dirty tab asks first (inline strip, no browser
 * confirm), background refetches never clobber a dirty buffer (reconcileServer),
 * diff cards / search open a file at a line, and Propose uses the forked
 * `base_sha` then clears the buffer and routes the review into the chat rail.
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { OnMount } from '@monaco-editor/react';
import { FileWarning, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { toast } from '@/components/ui/toast';
import { ApiError } from '@/lib/api/client';
import { createPatch } from '@/lib/api/patches';
import { getFile, type FileContent } from '@/lib/api/workspace';
import { languageForPath } from '@/lib/ide/language';
import { ThemedMonacoDiff, ThemedMonacoEditor } from '@/lib/ide/monaco';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';

type EditorInstance = Parameters<OnMount>[0];

export function EditorPane({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const tabs = useIdeStore((s) => s.tabs);
  const active = useIdeStore((s) => s.active);
  const buffers = useIdeStore((s) => s.buffers);
  const setActive = useIdeStore((s) => s.setActive);
  const setBuffer = useIdeStore((s) => s.setBuffer);
  const requestCloseTab = useIdeStore((s) => s.requestCloseTab);
  const forceCloseTab = useIdeStore((s) => s.forceCloseTab);
  const reconcileServer = useIdeStore((s) => s.reconcileServer);
  const pendingReveal = useIdeStore((s) => s.pendingReveal);
  const clearReveal = useIdeStore((s) => s.clearReveal);
  const setRightTab = useIdeStore((s) => s.setRightTab);

  const editorRef = useRef<EditorInstance | null>(null);
  const [confirmClose, setConfirmClose] = useState<string | null>(null);
  const [reviewOpen, setReviewOpen] = useState(false);

  const file = useQuery<FileContent, ApiError>({
    queryKey: ['file', projectId, active],
    queryFn: () => getFile(projectId, active as string),
    enabled: Boolean(active),
  });

  // Drop a buffer whose edit has landed on disk; never overwrite a still-diff buffer.
  useEffect(() => {
    if (!active || !file.data || file.data.binary || file.data.content == null) return;
    reconcileServer(active, file.data.content);
  }, [active, file.data, reconcileServer]);

  // Consume a pending reveal once the target file is active + loaded.
  useEffect(() => {
    if (!pendingReveal || pendingReveal.path !== active) return;
    if (!file.data || file.data.binary) return;
    const editor = editorRef.current;
    if (!editor) return;
    editor.revealLineInCenter(pendingReveal.line);
    editor.setPosition({ lineNumber: pendingReveal.line, column: 1 });
    editor.focus();
    clearReveal();
  }, [pendingReveal, active, file.data, clearReveal]);

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor;
    const state = useIdeStore.getState();
    if (state.pendingReveal && state.pendingReveal.path === state.active) {
      editor.revealLineInCenter(state.pendingReveal.line);
      editor.setPosition({ lineNumber: state.pendingReveal.line, column: 1 });
      state.clearReveal();
    }
  };

  const propose = useMutation({
    mutationFn: () => {
      const buf = buffers[active as string];
      return createPatch(projectId, {
        summary: `Edit ${active}`,
        files: [
          {
            path: active as string,
            change_type: 'modify',
            base_sha: buf.baseSha,
            new_content: buf.content,
          },
        ],
      });
    },
    onSuccess: () => {
      if (active && file.data && file.data.content != null) {
        // Clear the buffer: the edit is now a pending patch.
        setBuffer(active, file.data.content, file.data.content, file.data.sha);
      }
      void queryClient.invalidateQueries({ queryKey: ['patches', projectId] });
      toast({ title: t('ide.patchProposed') });
      setRightTab('chat');
    },
    onError: (err) =>
      toast({
        title: t('ide.proposeFailed'),
        description: err instanceof Error ? err.message : undefined,
        variant: 'error',
      }),
  });

  const buffer = active ? buffers[active] : undefined;
  const value = active ? (buffer?.content ?? file.data?.content ?? '') : '';
  const dirty = buffer !== undefined;
  const onDiskChanged = Boolean(buffer && file.data && buffer.baseSha !== file.data.sha);
  const denied = file.error?.status === 403;
  const notFound = file.error?.status === 404;

  const closeTab = (path: string) => {
    if (requestCloseTab(path) === 'needs-confirm') setConfirmClose(path);
  };

  return (
    <div className="flex h-full flex-col bg-bg">
      {/* Tab bar */}
      <div className="flex items-center border-b border-border bg-surface">
        {tabs.length === 0 && (
          <span className="px-4 py-2.5 text-xs text-muted">{t('ide.openFilePrompt')}</span>
        )}
        <div className="flex min-w-0 flex-1 overflow-x-auto">
          {tabs.map((path) => {
            const name = path.split('/').pop() ?? path;
            const isDirty = buffers[path] !== undefined;
            return (
              <div
                key={path}
                className={
                  'group flex shrink-0 items-center gap-2 border-r border-border px-3 py-2.5 text-xs font-medium ' +
                  (active === path
                    ? 'border-t-2 border-t-accent bg-bg text-text'
                    : 'text-muted hover:bg-surface-2')
                }
              >
                <button type="button" onClick={() => setActive(path)} className="flex items-center gap-2 outline-none">
                  <span
                    className={isDirty ? 'text-warn' : 'text-faint'}
                    aria-label={isDirty ? t('ide.unsavedDot') : undefined}
                  >
                    {isDirty ? '●' : '○'}
                  </span>
                  {name}
                </button>
                <button
                  type="button"
                  aria-label={t('common.close')}
                  onClick={() => closeTab(path)}
                  className="rounded p-0.5 text-faint hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
                >
                  <X className="h-3 w-3" aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>
        {active && !denied && !notFound && (
          <div className="ml-auto shrink-0 px-3">
            <Button
              size="sm"
              onClick={() => propose.mutate()}
              disabled={!dirty || propose.isPending}
              loading={propose.isPending}
            >
              {dirty ? t('ide.proposePatch') : t('ide.reviewed')}
            </Button>
          </div>
        )}
      </div>

      {/* Inline close-confirm strip */}
      {confirmClose && (
        <div className="flex items-center gap-2 border-b border-warn/40 bg-warn-bg px-3 py-1.5 text-xs text-warn">
          <span className="flex-1">
            {t('ide.discardPrompt', { name: confirmClose.split('/').pop() ?? confirmClose })}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              forceCloseTab(confirmClose);
              setConfirmClose(null);
            }}
          >
            {t('ide.discard')}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setConfirmClose(null)}>
            {t('ide.keep')}
          </Button>
        </div>
      )}

      {/* On-disk change chip */}
      {onDiskChanged && (
        <div className="flex items-center gap-2 border-b border-info/40 bg-info-bg px-3 py-1.5 text-xs text-info">
          <FileWarning className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="flex-1">{t('ide.fileChangedOnDisk')}</span>
          <Button variant="outline" size="sm" onClick={() => setReviewOpen(true)}>
            {t('ide.review')}
          </Button>
        </div>
      )}

      {/* Editor body */}
      <div className="relative flex-1">
        {!active && (
          <div className="flex h-full items-center justify-center text-sm text-faint">
            {t('ide.noFileOpen')}
          </div>
        )}
        {active && file.isLoading && (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            {t('ide.loadingFile')}
          </div>
        )}
        {active && denied && (
          <div className="flex h-full items-center justify-center text-sm text-danger">
            {t('ide.protectedFile')}
          </div>
        )}
        {active && notFound && (
          <div className="flex h-full items-center justify-center text-sm text-danger">
            {t('ide.fileNotFound')}
          </div>
        )}
        {active && file.data?.binary && (
          <div className="flex h-full items-center justify-center text-sm text-muted">
            {t('ide.binaryPreview')}
          </div>
        )}
        {active && file.data && !file.data.binary && (
          <ThemedMonacoEditor
            height="100%"
            language={languageForPath(active)}
            value={value}
            onMount={handleMount}
            onChange={(next?: string) =>
              setBuffer(active, next ?? '', file.data?.content ?? '', file.data?.sha ?? null)
            }
            options={{ lineNumbers: 'on', renderLineHighlight: 'line' }}
          />
        )}
      </div>

      {/* Review buffer vs on-disk content */}
      <Dialog open={reviewOpen} onOpenChange={setReviewOpen}>
        <DialogContent size="lg" className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="truncate font-mono text-sm">{active}</DialogTitle>
            <DialogClose />
          </DialogHeader>
          {active && file.data && (
            <div className="h-[70vh] border-t border-border">
              <ThemedMonacoDiff
                height="100%"
                language={languageForPath(active)}
                original={file.data.content ?? ''}
                modified={buffer?.content ?? ''}
              />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
