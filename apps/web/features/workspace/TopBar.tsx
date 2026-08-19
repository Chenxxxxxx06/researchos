'use client';

import { Search } from 'lucide-react';
import Link from 'next/link';

import { Kbd } from '@/components/ui/kbd';
import type { MeResponse } from '@/lib/api/auth';
import { useCommandStore } from '@/lib/command/registry';
import { useI18n } from '@/lib/i18n';

import { LanguageSwitcher } from './LanguageSwitcher';
import { OrgSwitcher } from './OrgSwitcher';
import { ProjectSwitcher } from './ProjectSwitcher';
import { RuntimeStatus } from './RuntimeStatus';
import { ThemeToggle } from './ThemeToggle';
import { UserMenu } from './UserMenu';

export function TopBar({ me }: { me: MeResponse }) {
  const { t } = useI18n();
  const setPaletteOpen = useCommandStore((state) => state.setOpen);

  return (
    <header className="desktop-drag-region sticky top-0 z-30 flex h-16 shrink-0 items-center justify-between gap-3 border-b border-border bg-surface/92 px-3 backdrop-blur-xl sm:px-4">
      <div className="desktop-no-drag flex min-w-0 items-center gap-2 sm:gap-3">
        <Link
          href="/projects"
          className="group flex shrink-0 items-center gap-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
        >
          <span className="grid h-8 w-8 place-items-center rounded-md bg-accent text-sm font-bold text-accent-fg shadow-elev1 transition-transform group-hover:-translate-y-0.5">R</span>
          <span className="hidden text-sm font-semibold tracking-[-0.025em] text-text md:block">{t('app.name')}</span>
        </Link>
        <span className="hidden h-5 w-px bg-border md:block" aria-hidden="true" />
        <div className="hidden min-w-0 sm:block">
          <OrgSwitcher organizations={me.organizations} />
        </div>
        <ProjectSwitcher />
      </div>

      <div className="desktop-no-drag flex shrink-0 items-center gap-1.5">
        <RuntimeStatus />
        <button
          type="button"
          onClick={() => setPaletteOpen(true)}
          className="flex h-8 items-center gap-2 rounded-md border border-border bg-bg/70 px-2.5 text-sm text-muted shadow-elev1 hover:border-border-strong hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60 sm:min-w-36 sm:justify-between lg:min-w-48"
        >
          <span className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5" aria-hidden="true" />
            <span className="hidden sm:inline">{t('common.search')}</span>
          </span>
          <span className="hidden sm:inline-flex"><Kbd keys="mod+k" /></span>
        </button>
        <ThemeToggle />
        <LanguageSwitcher />
        <UserMenu me={me} />
      </div>
    </header>
  );
}
