'use client';

import Link from 'next/link';
import { Search } from 'lucide-react';

import type { MeResponse } from '@/lib/api/auth';
import { useCommandStore } from '@/lib/command/registry';
import { useI18n } from '@/lib/i18n';
import { Kbd } from '@/components/ui/kbd';

import { LanguageSwitcher } from './LanguageSwitcher';
import { OrgSwitcher } from './OrgSwitcher';
import { ProjectSwitcher } from './ProjectSwitcher';
import { ThemeToggle } from './ThemeToggle';
import { UserMenu } from './UserMenu';

export function TopBar({ me }: { me: MeResponse }) {
  const { t } = useI18n();
  const setPaletteOpen = useCommandStore((s) => s.setOpen);

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-surface/95 px-5 backdrop-blur">
      <div className="flex items-center gap-3">
        <Link
          href="/projects"
          className="text-[15px] font-bold tracking-tight text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
        >
          {t('app.name')}
        </Link>
        <OrgSwitcher organizations={me.organizations} />
        <ProjectSwitcher />
      </div>
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="flex h-8 items-center gap-2 rounded-md border border-border bg-surface px-2.5 text-sm text-muted hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
        >
          <Search className="h-3.5 w-3.5" aria-hidden="true" />
          <span className="hidden sm:inline">{t('common.search')}</span>
          <Kbd keys="mod+k" />
        </button>
        <ThemeToggle />
        <LanguageSwitcher />
        <UserMenu me={me} />
      </div>
    </header>
  );
}
