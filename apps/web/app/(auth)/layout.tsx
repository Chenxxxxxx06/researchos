'use client';

import type { ReactNode } from 'react';

import { useI18n } from '@/lib/i18n';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';

export default function AuthLayout({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <main className="relative flex min-h-screen items-center justify-center bg-neutral-50 p-6">
      <div className="absolute right-4 top-4">
        <LanguageSwitcher />
      </div>
      <div className="w-full max-w-sm">
        <div className="mb-6 text-center">
          <h1 className="text-xl font-bold tracking-tight">{t('app.name')}</h1>
          <p className="mt-1 text-sm text-neutral-500">{t('app.tagline')}</p>
        </div>
        {children}
      </div>
    </main>
  );
}
