'use client';

import { useEffect, useState } from 'react';

export type ResolvedTheme = 'light' | 'dark';

function readTheme(): ResolvedTheme {
  if (typeof document === 'undefined') return 'light';
  const attr = document.documentElement.dataset.theme;
  if (attr === 'dark' || attr === 'light') return attr;
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  return 'light';
}

/**
 * Resolve the active theme without importing any design-system module: read the
 * `data-theme` attribute the ThemeProvider stamps on `<html>`, observe it, and
 * fall back to the OS preference when the attribute is absent. Keeps this
 * partition buildable standalone.
 */
export function useResolvedTheme(): ResolvedTheme {
  const [theme, setTheme] = useState<ResolvedTheme>('light');

  useEffect(() => {
    setTheme(readTheme());

    const root = document.documentElement;
    const observer = new MutationObserver(() => setTheme(readTheme()));
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] });

    const media = window.matchMedia?.('(prefers-color-scheme: dark)');
    const onMedia = () => {
      if (!root.dataset.theme) setTheme(readTheme());
    };
    media?.addEventListener('change', onMedia);

    return () => {
      observer.disconnect();
      media?.removeEventListener('change', onMedia);
    };
  }, []);

  return theme;
}
