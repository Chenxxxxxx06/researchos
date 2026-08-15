'use client';

import Link from 'next/link';
import { usePathname, useParams } from 'next/navigation';
import {
  BookOpen,
  Code2,
  FileText,
  FlaskConical,
  FolderKanban,
  FolderCog,
  LayoutDashboard,
  MessagesSquare,
  Megaphone,
  Network,
  Route,
  Search,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';

import { useI18n, type DictKey } from '@/lib/i18n';
import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

interface NavItem {
  key: DictKey;
  segment: string;
  icon: LucideIcon;
  shortcut: string;
}

const ITEMS: NavItem[] = [
  { key: 'nav.overview', segment: 'overview', icon: LayoutDashboard, shortcut: 'g o' },
  { key: 'nav.missions', segment: 'missions', icon: Route, shortcut: 'g t' },
  { key: 'nav.orchestration', segment: 'orchestration', icon: Network, shortcut: 'g a' },
  { key: 'nav.research', segment: 'research', icon: Search, shortcut: 'g r' },
  { key: 'nav.references', segment: 'references', icon: BookOpen, shortcut: 'g l' },
  { key: 'nav.inbox', segment: 'inbox', icon: MessagesSquare, shortcut: 'g m' },
  { key: 'nav.ide', segment: 'ide', icon: Code2, shortcut: 'g i' },
  { key: 'nav.experiments', segment: 'experiments', icon: FlaskConical, shortcut: 'g e' },
  { key: 'nav.paper', segment: 'paper', icon: FileText, shortcut: 'g p' },
  { key: 'nav.reviewer', segment: 'reviewer', icon: ShieldCheck, shortcut: 'g v' },
  { key: 'nav.release', segment: 'release', icon: Megaphone, shortcut: 'g u' },
  { key: 'nav.manage', segment: 'manage', icon: FolderCog, shortcut: 'g n' },
];

const GROUPS: Array<{ key: DictKey; items: string[] }> = [
  { key: 'nav.groupCore', items: ['overview', 'missions', 'orchestration'] },
  { key: 'nav.groupResearch', items: ['research', 'references', 'inbox'] },
  { key: 'nav.groupBuild', items: ['ide', 'experiments'] },
  { key: 'nav.groupPublish', items: ['paper', 'reviewer', 'release'] },
  { key: 'nav.groupManage', items: ['manage'] },
];

export function SideRail() {
  const { t } = useI18n();
  const params = useParams<{ projectId?: string }>();
  const pathname = usePathname();
  const projectId = params?.projectId;

  // Path-boundary matching keeps nested routes attached to their parent item.
  const activeHref = ITEMS.reduce<string | null>((best, item) => {
    if (!projectId) return best;
    const href = `/projects/${projectId}/${item.segment}`;
    const matches = pathname === href || pathname?.startsWith(`${href}/`);
    if (matches && (!best || href.length > best.length)) return href;
    return best;
  }, null);

  return (
    <>
    <nav className="sticky top-14 hidden h-[calc(100dvh-3.5rem)] w-60 shrink-0 overflow-y-auto border-r border-border bg-surface/90 py-4 backdrop-blur lg:block">
      <Link
        href="/projects"
        className="mx-3 mb-5 flex items-center gap-2 rounded-md border border-transparent px-3 py-2 text-sm font-semibold text-text hover:border-border hover:bg-surface-2"
      >
        <FolderKanban className="h-4 w-4" aria-hidden="true" /> {t('nav.projects')}
      </Link>
      <div className="space-y-5 px-2">
        {GROUPS.map((group) => (
          <section key={group.key} aria-labelledby={`nav-${group.key}`}>
            <h2 id={`nav-${group.key}`} className="mb-1.5 px-3 text-[10px] font-semibold tracking-[0.16em] text-faint">
              {t(group.key).toUpperCase()}
            </h2>
            <ul className="space-y-0.5">
              {ITEMS.filter((item) => group.items.includes(item.segment)).map((item) => {
          const href = projectId ? `/projects/${projectId}/${item.segment}` : null;
          const active = href !== null && href === activeHref;
          const Icon = item.icon;
          return (
            <li key={item.key}>
              {href ? (
                <Tooltip content={t(item.key)} shortcut={item.shortcut} side="right" className="w-full">
                  <Link
                    href={href}
                    aria-current={active ? 'page' : undefined}
                    className={cn(
                      'relative flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                      active
                        ? 'bg-accent text-accent-fg shadow-sm before:absolute before:-left-2 before:h-5 before:w-0.5 before:bg-accent'
                        : 'text-muted hover:bg-surface-2 hover:text-text',
                    )}
                  >
                    <Icon className="h-4 w-4 shrink-0" aria-hidden="true" /> {t(item.key)}
                  </Link>
                </Tooltip>
              ) : (
                <span
                  aria-disabled="true"
                  className="flex cursor-not-allowed select-none items-center gap-2 rounded-lg px-3 py-2 text-sm text-faint"
                >
                  <Icon className="h-4 w-4 shrink-0" aria-hidden="true" /> {t(item.key)}
                </span>
              )}
            </li>
          );
              })}
            </ul>
          </section>
        ))}
      </div>
    </nav>
    <nav
      aria-label="Mobile workspace navigation"
      className="fixed inset-x-0 bottom-0 z-40 flex h-16 items-stretch overflow-x-auto border-t border-border bg-overlay/95 px-1 backdrop-blur lg:hidden"
    >
      {ITEMS.map((item) => {
        const href = projectId ? `/projects/${projectId}/${item.segment}` : null;
        const active = href !== null && href === activeHref;
        const Icon = item.icon;
        return href ? (
          <Link
            key={item.key}
            href={href}
            aria-current={active ? 'page' : undefined}
            className={cn(
              'flex w-[4.5rem] shrink-0 flex-col items-center justify-center gap-1 border-t-2 text-[9px] font-medium transition-colors',
              active
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-text',
            )}
          >
            <Icon className="h-4 w-4" aria-hidden="true" />
            <span className="max-w-[4.25rem] truncate">{t(item.key)}</span>
          </Link>
        ) : null;
      })}
    </nav>
    </>
  );
}
