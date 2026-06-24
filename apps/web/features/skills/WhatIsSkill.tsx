'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useI18n } from '@/lib/i18n';

export function WhatIsSkill() {
  const { t } = useI18n();

  return (
    <Card className="border-neutral-200 bg-neutral-50">
      <CardHeader>
        <CardTitle>{t('skills.whatIsTitle')}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm leading-relaxed text-neutral-600">{t('skills.whatIs')}</p>
      </CardContent>
    </Card>
  );
}
