'use client';

import { Languages } from 'lucide-react';

import { useI18n, type Locale } from '@/lib/i18n';
import { localeToLanguage, savePreferences } from '@/lib/theme/preferences';
import { Button } from '@/components/ui/button';
import { Dropdown, DropdownRadioItem } from '@/components/ui/dropdown';

const OPTIONS: Array<{ locale: Locale; label: string }> = [
  { locale: 'zh-CN', label: '中文' },
  { locale: 'en-US', label: 'English' },
];

export function LanguageSwitcher() {
  const { locale, setLocale, t } = useI18n();

  const choose = (next: Locale) => {
    setLocale(next);
    // Best-effort server sync (backend vocabulary: 'en' | 'zh-CN').
    void savePreferences({ language: localeToLanguage(next) });
  };

  return (
    <Dropdown
      align="end"
      trigger={
        <Button variant="ghost" size="icon" aria-label={t('common.language')}>
          <Languages className="h-4 w-4" aria-hidden="true" />
        </Button>
      }
    >
      {OPTIONS.map((option) => (
        <DropdownRadioItem
          key={option.locale}
          checked={locale === option.locale}
          onSelect={() => choose(option.locale)}
        >
          {option.label}
        </DropdownRadioItem>
      ))}
    </Dropdown>
  );
}
