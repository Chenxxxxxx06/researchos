'use client';

import { useI18n, type Locale } from '@/lib/i18n';

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();
  return (
    <select
      aria-label={t('common.language')}
      className="h-8 rounded-md border border-neutral-300 bg-white px-2 text-sm"
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
    >
      <option value="zh-CN">中文</option>
      <option value="en-US">English</option>
    </select>
  );
}
