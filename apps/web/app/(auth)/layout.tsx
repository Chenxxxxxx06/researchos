'use client';

import type { ReactNode } from 'react';

import { useI18n } from '@/lib/i18n';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';

export default function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-gradient-to-br from-neutral-50 via-white to-neutral-100 p-6">
      <div className="absolute right-6 top-6">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-neutral-900">
            <span className="text-xl font-bold text-white">R</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-neutral-900">{t('app.name')}</h1>
          <p className="mt-2 text-sm text-neutral-500">{t('app.tagline')}</p>
        </div>
        {children}
      </div>
    </main>
  );
}
