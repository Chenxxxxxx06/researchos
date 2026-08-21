/**
 * Monaco theme definitions matched to the semantic tokens.
 *
 * `monaco-editor` is a types-only devDependency (P3-D13: the editor core is
 * CDN-loaded by @monaco-editor/react) — only `import type` is allowed here.
 */

import type * as MonacoNs from 'monaco-editor';

import type { ResolvedTheme } from './preferences';

export const MONACO_LIGHT = 'ros-light';
export const MONACO_DARK = 'ros-dark';

type MonacoApi = { editor: Pick<typeof MonacoNs.editor, 'defineTheme'> };

/**
 * Register both ResearchOS themes on a Monaco instance. Safe to call more
 * than once (defineTheme overwrites). Wire as `beforeMount` on the editor.
 */
export function defineMonacoThemes(monaco: MonacoApi): void {
  monaco.editor.defineTheme(MONACO_LIGHT, {
    base: 'vs',
    inherit: true,
    rules: [],
    colors: {
      // --color-surface / --color-surface-2 (light)
      'editor.background': '#ffffff',
      'editorGutter.background': '#f7f8fa',
      'editor.lineHighlightBackground': '#f4f5f7',
      'editorLineNumber.foreground': '#9ca3af',
      'editorLineNumber.activeForeground': '#6b7280',
    },
  });
  monaco.editor.defineTheme(MONACO_DARK, {
    base: 'vs-dark',
    inherit: true,
    rules: [],
    colors: {
      // --color-surface / --color-surface-2 (dark)
      'editor.background': '#14171b',
      'editorGutter.background': '#14171b',
      'editor.lineHighlightBackground': '#1c2025',
      'editorLineNumber.foreground': '#6e7680',
      'editorLineNumber.activeForeground': '#9ba3ad',
    },
  });
}

export function monacoThemeFor(resolved: ResolvedTheme): string {
  return resolved === 'dark' ? MONACO_DARK : MONACO_LIGHT;
}
