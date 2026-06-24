'use client';

import Link from 'next/link';
import { Suspense } from 'react';

import { useI18n } from '@/lib/i18n';
import { Card, CardContent } from '@/components/ui/card';
import { LoginForm } from '@/features/auth/LoginForm';

export default function LoginPage() {
  const { t } = useI18n();
  return (
    <Card className="shadow-md">
      <CardContent className="p-6">
        <h2 className="mb-5 text-base font-semibold text-neutral-900">{t('auth.signInTitle')}</h2>
        <Suspense fallback={null}>
          <LoginForm />
        </Suspense>
        <p className="mt-5 text-center text-sm text-neutral-500">
          {t('auth.noAccount')}{' '}
          <Link href="/register" className="font-medium text-neutral-900 underline decoration-neutral-300 hover:decoration-neutral-900">
            {t('auth.createOne')}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
