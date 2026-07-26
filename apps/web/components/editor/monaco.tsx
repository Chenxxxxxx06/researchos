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

import { defineMonacoThemes, monacoThemeFor } from '@/lib/theme/monaco';
import { useTheme } from '@/lib/theme';

const BaseEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false });
const BaseDiff = dynamic(
  () => import('@monaco-editor/react').then((m) => ({ default: m.DiffEditor })),
  { ssr: false },
);

export function MonacoEditor({ beforeMount, theme, ...props }: EditorProps) {
  const { resolved } = useTheme();
  return (
    <BaseEditor
      {...props}
      beforeMount={(monaco: Monaco) => {
        defineMonacoThemes(monaco);
        beforeMount?.(monaco);
      }}
      theme={theme ?? monacoThemeFor(resolved)}
    />
  );
}

export function MonacoDiff({ beforeMount, theme, ...props }: DiffEditorProps) {
  const { resolved } = useTheme();
  return (
    <BaseDiff
      {...props}
      beforeMount={(monaco: Monaco) => {
        defineMonacoThemes(monaco);
        beforeMount?.(monaco);
      }}
      theme={theme ?? monacoThemeFor(resolved)}
    />
  );
}
