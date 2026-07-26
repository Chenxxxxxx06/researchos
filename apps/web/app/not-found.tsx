'use client';

import Link from 'next/link';
import { Compass } from 'lucide-react';

import { useI18n } from '@/lib/i18n';
import { EmptyState } from '@/components/ui/empty-state';

export default function NotFoundPage() {
  const { t } = useI18n();
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-6">
      <EmptyState
        icon={Compass}
        title={t('errors.notFoundTitle')}
        body={t('errors.notFoundBody')}
        actions={
          <Link
            href="/projects"
            className="inline-flex h-10 items-center justify-center rounded-md border border-border-strong bg-surface px-4 text-sm font-medium text-text hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
          >
            {t('errors.backHome')}
          </Link>
        }
        className="w-full max-w-md border-none"
      />
    </main>
  );
}
