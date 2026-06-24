'use client';

import Link from 'next/link';
import { usePathname, useParams } from 'next/navigation';

import { useI18n, type DictKey } from '@/lib/i18n';
import { cn } from '@/lib/utils';

interface NavItem { key: DictKey; segment: string | null; icon: string; }

const ITEMS: NavItem[] = [
  { key: 'nav.overview', segment: 'overview', icon: '🏠' },
  { key: 'nav.research', segment: 'research', icon: '🔍' },
  { key: 'nav.ide', segment: 'ide', icon: '⌨️' },
  { key: 'nav.experiments', segment: 'experiments', icon: '📊' },
  { key: 'nav.paper', segment: 'paper', icon: '📝' },
  { key: 'nav.skills', segment: 'skills', icon: '🧩' },
  { key: 'nav.skillBuilder', segment: 'skills/builder', icon: '🛠️' },
  { key: 'nav.settings', segment: 'settings', icon: '⚙️' },
];

export function SideRail() {
  const { t } = useI18n();
  const params = useParams<{ projectId?: string }>();
  const pathname = usePathname();
  const projectId = params?.projectId;

  return (
    <nav className="w-52 shrink-0 border-r border-neutral-200 bg-white/80 py-3">
      <Link href="/projects" className="mx-3 mb-4 flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-100">
        📁 {t('nav.projects')}
      </Link>
      <ul className="space-y-0.5 px-2">
        {ITEMS.map((item) => {
          const href = projectId && item.segment ? `/projects/${projectId}/${item.segment}` : null;
          const active = href && pathname?.startsWith(href);
          return (
            <li key={item.key}>
              {href ? (
                <Link href={href} className={cn(
                  'flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                  active ? 'bg-neutral-900 text-white' : 'text-neutral-600 hover:bg-neutral-100',
                )}>
                  <span className="text-base">{item.icon}</span> {t(item.key)}
                </Link>
              ) : (
                <span className="flex cursor-not-allowed items-center gap-2 rounded-lg px-3 py-2 text-sm text-neutral-300 select-none">
                  <span className="text-base">{item.icon}</span> {t(item.key)}
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
