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
        <h2 className="mb-4 text-base font-semibold">{t('auth.signInTitle')}</h2>
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
        <p className="mt-4 text-center text-sm text-neutral-500">
          {t('auth.noAccount')}{' '}
          <Link href="/register" className="font-medium text-neutral-900 underline">
            {t('auth.createOne')}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
