'use client';

import { useQuery } from '@tanstack/react-query';

import { getFile } from '@/lib/api/workspace';
import type { PatchFile } from '@/lib/api/patches';
import { languageForPath } from '@/lib/ide/language';
import { MonacoDiff } from '@/lib/ide/monaco';
import { Skeleton } from '@/components/ui/skeleton';

export function PatchDiff({ projectId, file }: { projectId: string; file: PatchFile }) {
  const original = useQuery({
    queryKey: ['file', projectId, file.path],
    queryFn: () => getFile(projectId, file.path),
    enabled: file.change_type !== 'create', retry: false,
  });
  const originalContent = file.change_type === 'create' ? '' : (original.data?.content ?? '');

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-200">
      <div className="flex items-center justify-between bg-neutral-50 px-3 py-1.5">
        <span className="font-mono text-[11px] font-medium text-neutral-700">{file.path}</span>
        <span className="rounded-full bg-neutral-200 px-2 py-0.5 text-[10px] font-medium text-neutral-600">{file.change_type}</span>
      </div>
      {original.isLoading ? <Skeleton className="h-[140px]" /> : (
        <MonacoDiff height="180px" language={languageForPath(file.path)} original={originalContent} modified={file.new_content ?? ''}
          options={{ readOnly: true, minimap: { enabled: false }, renderSideBySide: false, fontSize: 12 }} />
      )}
    </div>
  );
}
