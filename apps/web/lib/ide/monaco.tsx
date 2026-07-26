'use client';

/**
 * Thin re-export of the canonical themed Monaco wrappers (CONSOLIDATION §9).
 * The raw `MonacoEditor` / `MonacoDiff` names are preserved so non-owned
 * consumers that still import `@/lib/ide/monaco` keep building AND gain
 * light/dark theming for free. `Themed*` variants bake in the shared IDE
 * default options.
 *
 * Monaco stays CDN-loaded (P3-D13); `monaco-editor` is a types-only devDep —
 * this module never runtime-imports it.
 */

import type { DiffEditorProps, EditorProps } from '@monaco-editor/react';

import { MonacoDiff, MonacoEditor } from '@/components/editor/monaco';

export { MonacoEditor, MonacoDiff };

const DEFAULT_EDITOR_OPTIONS: EditorProps['options'] = {
  minimap: { enabled: false },
  fontSize: 13,
  scrollBeyondLastLine: false,
};

export function ThemedMonacoEditor({ options, ...props }: EditorProps) {
  return <MonacoEditor {...props} options={{ ...DEFAULT_EDITOR_OPTIONS, ...options }} />;
}

export function ThemedMonacoDiff({ options, ...props }: DiffEditorProps) {
  return (
    <MonacoDiff
      {...props}
      options={{ ...DEFAULT_EDITOR_OPTIONS, readOnly: true, renderSideBySide: false, ...options }}
    />
  );
}
