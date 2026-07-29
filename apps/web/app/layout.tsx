import type { Metadata } from 'next';
import type { ReactNode } from 'react';

import { Providers } from './providers';
import './globals.css';

export const metadata: Metadata = {
  title: 'ResearchOS',
  description: 'AI-native research operating system.',
  applicationName: 'ResearchOS',
  authors: [{ name: 'Chenxxxxxx06', url: 'https://github.com/Chenxxxxxx06' }],
  creator: 'Chenxxxxxx06',
  publisher: 'Chenxxxxxx06',
  other: {
    copyright: 'Copyright (c) 2024-2026 Chenxxxxxx06. All rights reserved.',
    license: 'Proprietary',
  },
};

/**
 * FOUC-free boot: runs before first paint, resolves the stored theme
 * preference ('system' via matchMedia) onto <html data-theme>, and stamps
 * <html lang> from the stored locale. Keys mirror lib/theme ('ros-theme')
 * and lib/i18n ('ros_locale'). Guarded — storage failures fall through.
 */
const BOOT_SCRIPT = `(function () {
  try {
    var doc = document.documentElement;
    var pref = localStorage.getItem('ros-theme');
    var resolved =
      pref === 'light' || pref === 'dark'
        ? pref
        : window.matchMedia('(prefers-color-scheme: dark)').matches
          ? 'dark'
          : 'light';
    doc.setAttribute('data-theme', resolved);
    var locale = localStorage.getItem('ros_locale');
    if (locale === 'en-US' || locale === 'zh-CN') doc.setAttribute('lang', locale);
  } catch (e) {}
})();`;

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    // suppressHydrationWarning: the boot script mutates data-theme/lang on
    // <html> before hydration; the default lang matches the default locale.
    <html lang="zh-CN" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: BOOT_SCRIPT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
