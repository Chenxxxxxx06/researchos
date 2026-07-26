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
      'editorGutter.background': '#ffffff',
      'editor.lineHighlightBackground': '#f5f5f5',
      'editorLineNumber.foreground': '#a3a3a3',
      'editorLineNumber.activeForeground': '#737373',
    },
  });
  monaco.editor.defineTheme(MONACO_DARK, {
    base: 'vs-dark',
    inherit: true,
    rules: [],
    colors: {
      // --color-surface / --color-surface-2 (dark)
      'editor.background': '#18181b',
      'editorGutter.background': '#18181b',
      'editor.lineHighlightBackground': '#27272a',
      'editorLineNumber.foreground': '#71717a',
      'editorLineNumber.activeForeground': '#a1a1aa',
    },
  });
}

export function monacoThemeFor(resolved: ResolvedTheme): string {
  return resolved === 'dark' ? MONACO_DARK : MONACO_LIGHT;
}
