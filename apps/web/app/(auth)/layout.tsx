'use client';

import type { ReactNode } from 'react';

import { useI18n } from '@/lib/i18n';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';
import { ThemeToggle } from '@/features/workspace/ThemeToggle';

export default function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-gradient-to-br from-bg via-surface to-surface-2 p-6">
      <div className="absolute right-6 top-6 flex items-center gap-1.5">
        <ThemeToggle />
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-accent">
            <span className="text-xl font-bold text-accent-fg">R</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-text">{t('app.name')}</h1>
          <p className="mt-2 text-sm text-muted">{t('app.tagline')}</p>
        </div>
        {children}
      </div>
    </main>
  );
}
