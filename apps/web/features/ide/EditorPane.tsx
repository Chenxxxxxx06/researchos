'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError } from '@/lib/api/client';
import { createPatch } from '@/lib/api/patches';
import { getFile, type FileContent } from '@/lib/api/workspace';
import { languageForPath } from '@/lib/ide/language';
import { MonacoEditor } from '@/lib/ide/monaco';
import { useIdeStore } from '@/lib/store/ide';

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
    mutationFn: () => createPatch(projectId, {
      summary: `Edit ${active}`,
      files: [{ path: active as string, change_type: 'modify', base_sha: file.data?.sha ?? null, new_content: buffers[active as string] ?? file.data?.content ?? '' }],
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
      <div className="flex items-center gap-0 border-b border-neutral-200 bg-neutral-50">
        {tabs.length === 0 && <span className="px-4 py-2.5 text-xs text-neutral-400">Open a file from the explorer to start editing</span>}
        {tabs.map((path) => {
          const name = path.split('/').pop() ?? path;
          const isDirty = buffers[path] !== undefined;
          return (
            <button key={path} onClick={() => setActive(path)}
              className={`flex items-center gap-2 border-r border-neutral-200 px-4 py-2.5 text-xs font-medium transition-colors ${
                active === path ? 'border-t-2 border-t-neutral-900 bg-white text-neutral-900' : 'text-neutral-500 hover:bg-white/50'
              }`}>
              <span className={isDirty ? 'text-amber-500' : 'text-neutral-300'}>{isDirty ? '●' : '○'}</span>
              {name}
              <span className="ml-1 rounded px-1 text-[10px] text-neutral-400 hover:bg-neutral-200 hover:text-neutral-700" onClick={(e) => { e.stopPropagation(); closeTab(path); }}>×</span>
            </button>
          );
        })}
        {active && !denied && !notFound && (
          <div className="ml-auto px-3">
            <button onClick={() => propose.mutate()} disabled={!dirty || propose.isPending}
              className="rounded-lg bg-neutral-900 px-3 py-1.5 text-[11px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-40">
              {propose.isPending ? 'Proposing…' : dirty ? 'Propose patch' : '✓ Reviewed'}
            </button>
          </div>
        )}
      </div>

      {/* Editor body */}
      <div className="relative flex-1">
        {!active && <div className="flex h-full items-center justify-center text-sm text-neutral-300">⌨️ No file open</div>}
        {active && file.isLoading && <div className="flex h-full items-center justify-center text-sm text-neutral-400">Loading…</div>}
        {active && denied && <div className="flex h-full items-center justify-center text-sm text-red-500">🔒 Protected file — read-only denied</div>}
        {active && notFound && <div className="flex h-full items-center justify-center text-sm text-red-500">File not found</div>}
        {active && file.data?.binary && <div className="flex h-full items-center justify-center text-sm text-neutral-400">Binary or oversized — preview unavailable</div>}
        {active && file.data && !file.data.binary && (
          <MonacoEditor height="100%" language={languageForPath(active)} value={value}
            onChange={(v?: string) => setBuffer(active, v ?? '')}
            options={{ minimap: { enabled: false }, fontSize: 13, lineNumbers: 'on', renderLineHighlight: 'line', scrollBeyondLastLine: false }} />
        )}
      </div>
    </div>
  );
}
