'use client';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useI18n } from '@/lib/i18n';

export function SkillBuilderHelp() {
  const { t } = useI18n();

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('builder.help')}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-neutral-600">{t('builder.help')}</p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-neutral-600">
          <li>slug + name + version → manifest identity</li>
          <li>modules / 模块 → where the skill applies</li>
          <li>workflow → one step per line</li>
          <li>config schema → valid JSON object</li>
        </ul>
      </CardContent>
    </Card>
  );
}
