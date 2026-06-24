'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/api/client';
import { createPatch } from '@/lib/api/patches';
import { getFile, type FileContent } from '@/lib/api/workspace';
import { languageForPath } from '@/lib/ide/language';
import { MonacoEditor } from '@/lib/ide/monaco';
import { useIdeStore } from '@/lib/store/ide';
import { Button } from '@/components/ui/button';

export function EditorPane({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const tabs = useIdeStore((s) => s.tabs);
  const active = useIdeStore((s) => s.active);
  const setActive = useIdeStore((s) => s.setActive);
  const closeTab = useIdeStore((s) => s.closeTab);
  const buffers = useIdeStore((s) => s.buffers);
  const setBuffer = useIdeStore((s) => s.setBuffer);

  const file = useQuery<FileContent, ApiError>({
    queryKey: ['file', projectId, active],
    queryFn: () => getFile(projectId, active as string),
    enabled: Boolean(active),
  });

  const propose = useMutation({
    mutationFn: () =>
      createPatch(projectId, {
        summary: `Edit ${active}`,
        files: [
          {
            path: active as string,
            change_type: 'modify',
            base_sha: file.data?.sha ?? null,
            new_content: buffers[active as string] ?? file.data?.content ?? '',
          },
        ],
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['patches', projectId] }),
  });

  const value = active ? (buffers[active] ?? file.data?.content ?? '') : '';
  const dirty = Boolean(active && file.data && buffers[active] !== undefined && buffers[active] !== file.data.content);
  const denied = file.error?.status === 403;
  const notFound = file.error?.status === 404;

  return (
    <div className="flex h-full flex-col">
      {/* Tab bar */}
      <div className="flex items-center gap-1 border-b border-neutral-200 bg-white px-2">
        {tabs.length === 0 && (
          <span className="py-2 text-xs text-neutral-400">Open a file from the explorer</span>
        )}
        {tabs.map((path) => (
          <div
            key={path}
            className={`flex items-center gap-1 border-b-2 px-2 py-2 text-xs ${
              active === path ? 'border-neutral-900 text-neutral-900' : 'border-transparent text-neutral-500'
            }`}
          >
            <button onClick={() => setActive(path)}>{path.split('/').pop()}</button>
            <button className="text-neutral-400 hover:text-neutral-700" onClick={() => closeTab(path)}>
              ×
            </button>
          </div>
        ))}
        <div className="ml-auto flex items-center gap-2">
          {dirty && <span className="text-xs text-amber-600">● unsaved</span>}
          {active && !denied && !notFound && (
            <Button size="sm" variant="secondary" disabled={!dirty || propose.isPending} onClick={() => propose.mutate()}>
              {propose.isPending ? 'Proposing…' : 'Propose as patch'}
            </Button>
          )}
        </div>
      </div>

      {/* Editor body */}
      <div className="relative flex-1">
        {!active && (
          <div className="flex h-full items-center justify-center text-sm text-neutral-400">
            No file open
          </div>
        )}
        {active && file.isLoading && (
          <div className="flex h-full items-center justify-center text-sm text-neutral-400">Loading…</div>
        )}
        {active && denied && (
          <div className="flex h-full items-center justify-center text-sm text-red-600">
            This file is protected (read-only denied).
          </div>
        )}
        {active && notFound && (
          <div className="flex h-full items-center justify-center text-sm text-red-600">
            File not found.
          </div>
        )}
        {active && file.data && !file.data.binary && (
          <MonacoEditor
            height="100%"
            language={languageForPath(active)}
            value={value}
            onChange={(v?: string) => setBuffer(active, v ?? '')}
            options={{ minimap: { enabled: false }, fontSize: 13 }}
          />
        )}
        {active && file.data?.binary && (
          <div className="flex h-full items-center justify-center text-sm text-neutral-400">
            Binary or oversized file — preview unavailable.
          </div>
        )}
      </div>
    </div>
  );
}
