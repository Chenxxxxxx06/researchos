'use client';

import {
  BookOpen,
  Code2,
  FileText,
  FlaskConical,
  FolderCog,
  FolderKanban,
  Inbox,
  LayoutDashboard,
  Megaphone,
  MoreHorizontal,
  Network,
  Route,
  Search,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { useParams, usePathname, useRouter } from 'next/navigation';

import { Dropdown, DropdownItem, DropdownLabel, DropdownSeparator } from '@/components/ui/dropdown';
import { Tooltip } from '@/components/ui/tooltip';
import { useI18n, type DictKey } from '@/lib/i18n';
import { cn } from '@/lib/utils';

interface PrimaryNavItem {
  key: DictKey;
  segment: string;
  icon: LucideIcon;
  shortcut: string;
  owns: string[];
}

interface UtilityNavItem {
  key: DictKey;
  segment: string;
  icon: LucideIcon;
}

const PRIMARY_ITEMS: PrimaryNavItem[] = [
  { key: 'nav.overview', segment: 'overview', icon: LayoutDashboard, shortcut: 'g o', owns: ['overview'] },
  { key: 'nav.missions', segment: 'missions', icon: Route, shortcut: 'g t', owns: ['missions', 'orchestration'] },
  { key: 'nav.research', segment: 'research', icon: Search, shortcut: 'g r', owns: ['research', 'references', 'inbox', 'deadlines'] },
  { key: 'nav.ide', segment: 'ide', icon: Code2, shortcut: 'g i', owns: ['ide'] },
  { key: 'nav.experiments', segment: 'experiments', icon: FlaskConical, shortcut: 'g e', owns: ['experiments'] },
  { key: 'nav.paper', segment: 'paper', icon: FileText, shortcut: 'g p', owns: ['paper', 'reviewer'] },
  { key: 'nav.release', segment: 'release', icon: Megaphone, shortcut: 'g u', owns: ['release'] },
];

const UTILITY_ITEMS: UtilityNavItem[] = [
  { key: 'nav.orchestration', segment: 'orchestration', icon: Network },
  { key: 'nav.references', segment: 'references', icon: BookOpen },
  { key: 'nav.inbox', segment: 'inbox', icon: Inbox },
  { key: 'nav.reviewer', segment: 'reviewer', icon: ShieldCheck },
  { key: 'nav.manage', segment: 'manage', icon: FolderCog },
];

export function SideRail() {
  const { t } = useI18n();
  const params = useParams<{ projectId?: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const projectId = params?.projectId;
  const currentSegment = projectId
    ? pathname?.split(`/projects/${projectId}/`)[1]?.split('/')[0] ?? null
    : null;

  const hrefFor = (segment: string) => projectId ? `/projects/${projectId}/${segment}` : '/projects';

  return (
    <>
      <nav
        aria-label="Primary workspace navigation"
        className="sticky top-16 hidden h-[calc(100dvh-4rem)] w-[5.25rem] shrink-0 flex-col border-r border-border bg-surface/94 px-2 py-3 backdrop-blur-xl lg:flex"
      >
        <Tooltip content={t('nav.projects')} side="right">
          <Link
            href="/projects"
            aria-label={t('nav.projects')}
            className="mb-3 flex h-11 items-center justify-center rounded-md border border-border bg-surface-2 text-text shadow-elev1 hover:border-border-strong"
          >
            <FolderKanban className="h-[18px] w-[18px]" aria-hidden="true" />
          </Link>
        </Tooltip>

        <ul className="space-y-1">
          {PRIMARY_ITEMS.map((item) => {
            const active = item.owns.includes(currentSegment ?? '');
            const Icon = item.icon;
            return (
              <li key={item.key}>
                <Tooltip content={t(item.key)} shortcut={item.shortcut} side="right" className="w-full">
                  <Link
                    href={hrefFor(item.segment)}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'relative flex min-h-[3.25rem] w-full flex-col items-center justify-center gap-1 rounded-md px-1 py-2 text-[10px] font-medium leading-none',
                      active
                        ? 'bg-accent/10 text-accent before:absolute before:-left-2 before:h-6 before:w-0.5 before:rounded-r before:bg-accent'
                        : 'text-muted hover:bg-surface-2 hover:text-text',
                    )}
                  >
                    <Icon className="h-[18px] w-[18px]" aria-hidden="true" />
                    <span className="max-w-full truncate">{t(item.key)}</span>
                  </Link>
                </Tooltip>
              </li>
            );
          })}
        </ul>

        <div className="mt-auto pt-3">
          <Dropdown
            align="start"
            panelClassName="w-56"
            trigger={
              <button
                type="button"
                className="flex min-h-[3.25rem] w-full flex-col items-center justify-center gap-1 rounded-md px-1 py-2 text-[10px] font-medium text-muted hover:bg-surface-2 hover:text-text"
              >
                <MoreHorizontal className="h-[18px] w-[18px]" aria-hidden="true" />
                <span>{t('nav.more')}</span>
              </button>
            }
          >
            <DropdownLabel>{t('nav.groupManage')}</DropdownLabel>
            {UTILITY_ITEMS.map((item) => (
              <DropdownItem
                key={item.key}
                icon={item.icon}
                onSelect={() => router.push(hrefFor(item.segment))}
              >
                {t(item.key)}
              </DropdownItem>
            ))}
            <DropdownSeparator />
            <DropdownItem icon={FolderKanban} onSelect={() => router.push('/projects')}>
              {t('nav.allProjects')}
            </DropdownItem>
          </Dropdown>
        </div>
      </nav>

      <nav
        aria-label="Mobile workspace navigation"
        className="fixed inset-x-0 bottom-0 z-40 grid h-[4.25rem] grid-cols-6 border-t border-border bg-overlay/96 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
      >
        {PRIMARY_ITEMS.slice(0, 5).map((item) => {
          const active = item.owns.includes(currentSegment ?? '');
          const Icon = item.icon;
          return (
            <Link
              key={item.key}
              href={hrefFor(item.segment)}
              aria-current={active ? 'page' : undefined}
              className={cn(
                'flex min-w-0 flex-col items-center justify-center gap-1 border-t-2 px-1 text-[9px] font-medium',
                active ? 'border-accent text-accent' : 'border-transparent text-muted',
              )}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span className="max-w-full truncate">{t(item.key)}</span>
            </Link>
          );
        })}
        <Dropdown
          align="end"
          className="flex min-w-0"
          panelClassName="w-56"
          trigger={
            <button type="button" className="flex w-full flex-col items-center justify-center gap-1 border-t-2 border-transparent px-1 text-[9px] font-medium text-muted">
              <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
              <span>{t('nav.more')}</span>
            </button>
          }
        >
          {PRIMARY_ITEMS.slice(5).map((item) => (
            <DropdownItem key={item.key} icon={item.icon} onSelect={() => router.push(hrefFor(item.segment))}>
              {t(item.key)}
            </DropdownItem>
          ))}
          <DropdownSeparator />
          {UTILITY_ITEMS.map((item) => (
            <DropdownItem key={item.key} icon={item.icon} onSelect={() => router.push(hrefFor(item.segment))}>
              {t(item.key)}
            </DropdownItem>
          ))}
        </Dropdown>
      </nav>
    </>
  );
}
