'use client';

import { Monitor, Moon, Sun } from 'lucide-react';

import { useI18n } from '@/lib/i18n';
import { useTheme, type ThemePreference } from '@/lib/theme';
import { Button } from '@/components/ui/button';
import { Dropdown, DropdownRadioItem } from '@/components/ui/dropdown';
import { Tooltip } from '@/components/ui/tooltip';

const ICONS = { light: Sun, dark: Moon, system: Monitor } as const;

export function ThemeToggle() {
  const { t } = useI18n();
  const { preference, setTheme } = useTheme();
  const Icon = ICONS[preference];

  const options: Array<{ value: ThemePreference; label: string; icon: typeof Sun }> = [
    { value: 'light', label: t('theme.light'), icon: Sun },
    { value: 'dark', label: t('theme.dark'), icon: Moon },
    { value: 'system', label: t('theme.system'), icon: Monitor },
  ];

  return (
    <Tooltip content={t('theme.label')} side="bottom">
      <Dropdown
        align="end"
        trigger={
          <Button variant="ghost" size="icon" aria-label={t('theme.label')}>
            <Icon className="h-4 w-4" aria-hidden="true" />
          </Button>
        }
      >
        {options.map((option) => (
          <DropdownRadioItem
            key={option.value}
            icon={option.icon}
            checked={preference === option.value}
            onSelect={() => setTheme(option.value)}
          >
            {option.label}
          </DropdownRadioItem>
        ))}
      </Dropdown>
    </Tooltip>
  );
}
