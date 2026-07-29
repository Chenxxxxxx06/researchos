'use client';

import Link from 'next/link';
import { usePathname, useParams } from 'next/navigation';
import {
  BookOpen,
  CalendarClock,
  Code2,
  FileText,
  FlaskConical,
  FolderKanban,
  LayoutDashboard,
  MessagesSquare,
  Megaphone,
  Network,
  Search,
  Settings,
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
  { key: 'nav.research', segment: 'research', icon: Search, shortcut: 'g r' },
  { key: 'nav.references', segment: 'references', icon: BookOpen, shortcut: 'g l' },
  { key: 'nav.inbox', segment: 'inbox', icon: MessagesSquare, shortcut: 'g m' },
  { key: 'nav.orchestration', segment: 'orchestration', icon: Network, shortcut: 'g a' },
  { key: 'nav.deadlines', segment: 'deadlines', icon: CalendarClock, shortcut: 'g d' },
  { key: 'nav.ide', segment: 'ide', icon: Code2, shortcut: 'g i' },
  { key: 'nav.experiments', segment: 'experiments', icon: FlaskConical, shortcut: 'g e' },
  { key: 'nav.paper', segment: 'paper', icon: FileText, shortcut: 'g p' },
  { key: 'nav.reviewer', segment: 'reviewer', icon: ShieldCheck, shortcut: 'g v' },
  { key: 'nav.release', segment: 'release', icon: Megaphone, shortcut: 'g u' },
  { key: 'nav.settings', segment: 'settings', icon: Settings, shortcut: 'g s' },
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
    <nav className="w-52 shrink-0 border-r border-border bg-surface/80 py-3">
      <Link
        href="/projects"
        className="mx-3 mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-text hover:bg-surface-2"
      >
        <FolderKanban className="h-4 w-4" aria-hidden="true" /> {t('nav.projects')}
      </Link>
      <ul className="space-y-0.5 px-2">
        {ITEMS.map((item) => {
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
                      'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                      active ? 'bg-accent text-accent-fg' : 'text-muted hover:bg-surface-2 hover:text-text',
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
    </nav>
  );
}
