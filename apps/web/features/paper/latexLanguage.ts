'use client';

/**
 * Minimal LaTeX Monarch grammar + language config (partition: frontend-paper,
 * SHOULD). Registered idempotently in the editor's `beforeMount`. Monaco stays
 * CDN-loaded (P3-D13); `monaco-editor` is imported for TYPES ONLY.
 */

import type { Monaco } from '@monaco-editor/react';

export const LATEX_LANGUAGE_ID = 'latex';

let registered = false;

export function registerLatexLanguage(monaco: Monaco): void {
  if (registered) return;
  const langs = monaco.languages.getLanguages();
  if (langs.some((l) => l.id === LATEX_LANGUAGE_ID)) {
    registered = true;
    return;
  }
  registered = true;

  monaco.languages.register({ id: LATEX_LANGUAGE_ID });

  monaco.languages.setMonarchTokensProvider(LATEX_LANGUAGE_ID, {
    defaultToken: '',
    tokenizer: {
      root: [
        [/%.*$/, 'comment'],
        // \begin{env} / \end{env}
        [/(\\(?:begin|end))(\s*)(\{)([^}]*)(\})/, ['keyword', '', 'delimiter.curly', 'type', 'delimiter.curly']],
        // control words / symbols
        [/\\[a-zA-Z@]+/, 'keyword'],
        [/\\[^a-zA-Z@]/, 'keyword'],
        // display + inline math
        [/\$\$/, { token: 'string', next: '@displayMath' }],
        [/\$/, { token: 'string', next: '@inlineMath' }],
        [/[{}]/, 'delimiter.curly'],
        [/[[\]]/, 'delimiter.square'],
        [/[&~^_]/, 'operator'],
      ],
      inlineMath: [
        [/[^$\\]+/, 'string'],
        [/\\[a-zA-Z@]+/, 'keyword'],
        [/\\./, 'string.escape'],
        [/\$/, { token: 'string', next: '@pop' }],
      ],
      displayMath: [
        [/[^$\\]+/, 'string'],
        [/\\[a-zA-Z@]+/, 'keyword'],
        [/\\./, 'string.escape'],
        [/\$\$/, { token: 'string', next: '@pop' }],
      ],
    },
  });

  monaco.languages.setLanguageConfiguration(LATEX_LANGUAGE_ID, {
    comments: { lineComment: '%' },
    brackets: [
      ['{', '}'],
      ['[', ']'],
    ],
    autoClosingPairs: [
      { open: '{', close: '}' },
      { open: '[', close: ']' },
      { open: '$', close: '$' },
    ],
    surroundingPairs: [
      { open: '{', close: '}' },
      { open: '[', close: ']' },
      { open: '$', close: '$' },
    ],
  });
}
