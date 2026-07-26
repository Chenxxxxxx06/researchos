'use client';

import { AlertTriangle } from 'lucide-react';

import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  const { t } = useI18n();
  return (
    <main className="flex min-h-screen items-center justify-center bg-bg p-6">
      <EmptyState
        icon={AlertTriangle}
        title={t('errors.title')}
        body={
          <>
            <p>{t('errors.body')}</p>
            {error.digest && (
              <p className="mt-2 font-mono text-xs text-faint">digest: {error.digest}</p>
            )}
          </>
        }
        actions={<Button onClick={() => reset()}>{t('errors.retry')}</Button>}
        className="w-full max-w-md border-none"
      />
    </main>
  );
}
