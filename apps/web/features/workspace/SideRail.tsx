'use client';

import Link from 'next/link';
import { usePathname, useParams } from 'next/navigation';

import { useI18n, type DictKey } from '@/lib/i18n';
import { cn } from '@/lib/utils';

interface NavItem {
  key: DictKey;
  segment: string | null; // path segment under /projects/[id], or null for project list
}

const ITEMS: NavItem[] = [
  { key: 'nav.overview', segment: 'overview' },
  { key: 'nav.research', segment: 'research' },
  { key: 'nav.ide', segment: 'ide' },
  { key: 'nav.experiments', segment: 'experiments' },
  { key: 'nav.paper', segment: 'paper' },
  { key: 'nav.skills', segment: 'skills' },
  { key: 'nav.skillBuilder', segment: 'skills/builder' },
  { key: 'nav.settings', segment: 'settings' },
];

export function SideRail() {
  const { t } = useI18n();
  const params = useParams<{ projectId?: string }>();
  const pathname = usePathname();
  const projectId = params?.projectId;

  return (
    <nav className="w-52 shrink-0 border-r border-neutral-200 bg-white p-2">
      <Link
        href="/projects"
        className="mb-2 block rounded-md px-3 py-2 text-sm font-semibold text-neutral-700 hover:bg-neutral-100"
      >
        {t('nav.projects')}
      </Link>
      <ul className="space-y-1">
        {ITEMS.map((item) => {
          const href = projectId && item.segment ? `/projects/${projectId}/${item.segment}` : null;
          const active = href && pathname?.startsWith(href);
          if (!href) {
            return (
              <li key={item.key}>
                <span className="block cursor-not-allowed select-none rounded-md px-3 py-2 text-sm text-neutral-300">
                  {t(item.key)}
                </span>
              </li>
            );
          }
          return (
            <li key={item.key}>
              <Link
                href={href}
                className={cn(
                  'block rounded-md px-3 py-2 text-sm font-medium',
                  active ? 'bg-neutral-900 text-white' : 'text-neutral-700 hover:bg-neutral-100',
                )}
              >
                {t(item.key)}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
