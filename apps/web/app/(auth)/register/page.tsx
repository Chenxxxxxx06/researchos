'use client';

import Link from 'next/link';

import { useI18n } from '@/lib/i18n';
import { Card, CardContent } from '@/components/ui/card';
import { RegisterForm } from '@/features/auth/RegisterForm';

export default function RegisterPage() {
  const { t } = useI18n();
  return (
    <Card className="shadow-elev2">
      <CardContent className="p-6">
        <h2 className="mb-4 text-base font-semibold text-text">{t('auth.createAccount')}</h2>
        <RegisterForm />
        <p className="mt-4 text-center text-sm text-muted">
          {t('auth.haveAccount')}{' '}
          <Link
            href="/login"
            className="font-medium text-text underline decoration-border-strong hover:decoration-current"
          >
            {t('common.signIn')}
          </Link>
        </p>
      </CardContent>
    </Card>
  );
}
