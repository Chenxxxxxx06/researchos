'use client';

/**
 * Canonical themed Monaco wrappers (CONSOLIDATION §9). Consumers swap
 * `@/lib/ide/monaco` → `@/components/editor/monaco` and get token-matched
 * light/dark theming for free; an explicit `theme` prop still wins.
 *
 * Monaco stays CDN-loaded via @monaco-editor/react (P3-D13): the core is
 * imported dynamically with ssr disabled, and `monaco-editor` itself is a
 * types-only devDependency.
 */

import dynamic from 'next/dynamic';
import type { DiffEditorProps, EditorProps, Monaco } from '@monaco-editor/react';

import { Skeleton } from '@/components/ui/skeleton';
import { defineMonacoThemes, monacoThemeFor } from '@/lib/theme/monaco';
import { useTheme } from '@/lib/theme';

const BaseEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false });
const BaseDiff = dynamic(
  () => import('@monaco-editor/react').then((m) => ({ default: m.DiffEditor })),
  { ssr: false },
);

export function MonacoEditor({ beforeMount, theme, loading = <EditorLoading />, ...props }: EditorProps) {
  const { resolved } = useTheme();
  return (
    <BaseEditor
      {...props}
      loading={loading}
      beforeMount={(monaco: Monaco) => {
        defineMonacoThemes(monaco);
        beforeMount?.(monaco);
      }}
      theme={theme ?? monacoThemeFor(resolved)}
    />
  );
}

export function MonacoDiff({ beforeMount, theme, loading = <EditorLoading />, ...props }: DiffEditorProps) {
  const { resolved } = useTheme();
  return (
    <BaseDiff
      {...props}
      loading={loading}
      beforeMount={(monaco: Monaco) => {
        defineMonacoThemes(monaco);
        beforeMount?.(monaco);
      }}
      theme={theme ?? monacoThemeFor(resolved)}
    />
  );
}

function EditorLoading() {
  return (
    <div className="h-full min-h-52 bg-surface p-5" aria-label="Loading editor">
      <div className="flex h-full gap-4">
        <div className="w-8 space-y-3 pt-1">
          {[0, 1, 2, 3, 4, 5, 6].map((line) => <Skeleton key={line} className="h-3 w-full" />)}
        </div>
        <div className="flex-1 space-y-3 pt-1">
          <Skeleton className="h-3 w-2/3" />
          <Skeleton className="h-3 w-5/6" />
          <Skeleton className="h-3 w-1/2" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-3 w-3/5" />
        </div>
      </div>
    </div>
  );
}
