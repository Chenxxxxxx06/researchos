'use client';

import { useI18n } from '@/lib/i18n';
import { LanguageSwitcher } from '@/features/workspace/LanguageSwitcher';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export default function SettingsPage() {
  const { t } = useI18n();
  return (
    <div className="max-w-2xl space-y-6">
      <h1 className="text-lg font-semibold">{t('settings.title')}</h1>
      <Card>
        <CardHeader>
          <CardTitle>{t('settings.language')}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="mb-3 text-sm text-neutral-500">{t('settings.languageHint')}</p>
          <LanguageSwitcher />
        </CardContent>
      </Card>
    </div>
  );
}
