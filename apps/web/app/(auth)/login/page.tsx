'use client';

import Link from 'next/link';
import { Suspense } from 'react';

import { useI18n } from '@/lib/i18n';
import { Card, CardContent } from '@/components/ui/card';
import { LoginForm } from '@/features/auth/LoginForm';

export default function LoginPage() {
  const { t } = useI18n();
  return (
    <Card>
      <CardContent className="p-6">
        <h2 className="mb-5 text-sm font-semibold text-text">{t('auth.signInTitle')}</h2>
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
        <p className="mt-5 text-center text-sm text-muted">
          {t('auth.noAccount')}{' '}
          <Link
            href="/register"
            className="font-medium text-text underline decoration-border-strong hover:decoration-current"
          >
            {t('auth.createOne')}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
