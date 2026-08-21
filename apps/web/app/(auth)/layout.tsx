'use client';

import type { ReactNode } from 'react';

import { useI18n } from '@/lib/i18n';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';
import { ThemeToggle } from '@/features/workspace/ThemeToggle';

export default function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-bg p-6">
      <div className="absolute right-4 top-4 flex items-center gap-1.5">
        <ThemeToggle />
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-md border border-border bg-surface">
            <span className="text-base font-semibold text-accent">R</span>
          </div>
          <h1 className="text-xl font-semibold tracking-tight text-text">{t('app.name')}</h1>
          <p className="mt-1.5 text-sm text-muted">{t('app.tagline')}</p>
        </div>
        {children}
      </div>
    </main>
  );
}
