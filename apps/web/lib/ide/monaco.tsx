'use client';

import dynamic from 'next/dynamic';

// Monaco only runs in the browser (it needs `window`) and loads its core from a
// CDN via the @monaco-editor/react loader, so it is imported with ssr: false.
export const MonacoEditor = dynamic(() => import('@monaco-editor/react'), { ssr: false });

export const MonacoDiff = dynamic(
  () => import('@monaco-editor/react').then((m) => ({ default: m.DiffEditor })),
  { ssr: false },
);
