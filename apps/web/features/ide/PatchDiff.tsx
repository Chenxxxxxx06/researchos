'use client';

import { useQuery } from '@tanstack/react-query';

import { getFile } from '@/lib/api/workspace';
import type { PatchFile } from '@/lib/api/patches';
import { languageForPath } from '@/lib/ide/language';
import { MonacoDiff } from '@/lib/ide/monaco';

export function PatchDiff({ projectId, file }: { projectId: string; file: PatchFile }) {
  const original = useQuery({
    queryKey: ['file', projectId, file.path],
    queryFn: () => getFile(projectId, file.path),
    enabled: file.change_type !== 'create',
    retry: false,
  });

  const originalContent =
    file.change_type === 'create' ? '' : (original.data?.content ?? '');

  return (
    <div className="rounded border border-neutral-200">
      <div className="flex items-center justify-between bg-neutral-50 px-2 py-1 text-xs">
        <span className="font-mono text-neutral-700">{file.path}</span>
        <span className="rounded bg-neutral-200 px-1.5 text-[10px] text-neutral-600">
          {file.change_type}
        </span>
      </div>
      <MonacoDiff
        height="220px"
        language={languageForPath(file.path)}
        original={originalContent}
        modified={file.new_content ?? ''}
        options={{ readOnly: true, minimap: { enabled: false }, renderSideBySide: false, fontSize: 12 }}
      />
    </div>
  );
}
