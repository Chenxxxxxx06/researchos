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
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type PointerEvent as ReactPointerEvent,
} from 'react';

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

const DEFAULT_RAIL_WIDTH = 84;
const MIN_RAIL_WIDTH = 76;
const MAX_RAIL_WIDTH = 240;
const EXPANDED_RAIL_WIDTH = 148;
const RAIL_STORAGE_KEY = 'researchos-side-rail-width';

function clampRailWidth(width: number): number {
  return Math.min(MAX_RAIL_WIDTH, Math.max(MIN_RAIL_WIDTH, Math.round(width)));
}

export function SideRail() {
  const { t } = useI18n();
  const params = useParams<{ projectId?: string }>();
  const pathname = usePathname();
  const router = useRouter();
  const projectId = params?.projectId;
  const currentSegment = projectId
    ? pathname?.split(`/projects/${projectId}/`)[1]?.split('/')[0] ?? null
    : null;
  const railRef = useRef<HTMLElement>(null);
  const [railWidth, setRailWidth] = useState(DEFAULT_RAIL_WIDTH);
  const [hasLoadedRailWidth, setHasLoadedRailWidth] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const isExpanded = railWidth >= EXPANDED_RAIL_WIDTH;

  useEffect(() => {
    const savedWidth = Number.parseInt(window.localStorage.getItem(RAIL_STORAGE_KEY) ?? '', 10);
    if (Number.isFinite(savedWidth)) setRailWidth(clampRailWidth(savedWidth));
    setHasLoadedRailWidth(true);
  }, []);

  useEffect(() => {
    if (!hasLoadedRailWidth) return;
    window.localStorage.setItem(RAIL_STORAGE_KEY, String(railWidth));
  }, [hasLoadedRailWidth, railWidth]);

  useEffect(() => {
    if (!isResizing) return;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';

    const onPointerMove = (event: PointerEvent) => {
      const left = railRef.current?.getBoundingClientRect().left ?? 0;
      setRailWidth(clampRailWidth(event.clientX - left));
    };
    const onPointerUp = () => setIsResizing(false);
    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp, { once: true });
    return () => {
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
      window.removeEventListener('pointermove', onPointerMove);
      window.removeEventListener('pointerup', onPointerUp);
    };
  }, [isResizing]);

  const beginResize = useCallback((event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    setIsResizing(true);
  }, []);

  const resizeWithKeyboard = useCallback((event: ReactKeyboardEvent<HTMLDivElement>) => {
    let nextWidth: number | null = null;
    if (event.key === 'ArrowLeft') nextWidth = railWidth - 16;
    if (event.key === 'ArrowRight') nextWidth = railWidth + 16;
    if (event.key === 'Home') nextWidth = MIN_RAIL_WIDTH;
    if (event.key === 'End') nextWidth = MAX_RAIL_WIDTH;
    if (event.key === 'Enter') nextWidth = DEFAULT_RAIL_WIDTH;
    if (nextWidth === null) return;
    event.preventDefault();
    setRailWidth(clampRailWidth(nextWidth));
  }, [railWidth]);

  const hrefFor = (segment: string) => projectId ? `/projects/${projectId}/${segment}` : '/projects';

  return (
    <>
      <nav
        ref={railRef}
        aria-label="Primary workspace navigation"
        className={cn(
          'sticky top-16 hidden h-[calc(100dvh-4rem)] shrink-0 flex-col border-r border-border bg-surface/94 px-2 py-3 backdrop-blur-xl lg:flex',
          isResizing ? 'transition-none' : 'transition-[width] duration-200 ease-out',
        )}
        style={{ width: railWidth }}
      >
        <Tooltip content={t('nav.projects')} side="right" className="w-full">
          <Link
            href="/projects"
            aria-label={t('nav.projects')}
            className={cn(
              'mb-3 flex h-[3.25rem] w-full items-center rounded-md border border-border bg-surface-2 text-text shadow-elev1 hover:border-border-strong',
              isExpanded ? 'justify-start gap-3 px-3 text-sm font-medium' : 'justify-center',
            )}
          >
            <FolderKanban className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
            {isExpanded && <span className="truncate">{t('nav.projects')}</span>}
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
                      'relative flex h-[3.25rem] w-full items-center rounded-md font-medium',
                      isExpanded
                        ? 'flex-row justify-start gap-3 px-3 text-sm'
                        : 'flex-col justify-center gap-1 px-1 text-[10px] leading-none',
                      active
                        ? 'bg-accent/10 text-accent before:absolute before:-left-2 before:h-6 before:w-0.5 before:rounded-r before:bg-accent'
                        : 'text-muted hover:bg-surface-2 hover:text-text',
                    )}
                  >
                    <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                    <span className="max-w-full truncate">{t(item.key)}</span>
                    {isExpanded && (
                      <span className="ml-auto shrink-0 font-mono text-[9px] tracking-wide text-faint">
                        {item.shortcut}
                      </span>
                    )}
                  </Link>
                </Tooltip>
              </li>
            );
          })}
        </ul>

        <div className="mt-auto pt-3">
          <Dropdown
            align="start"
            className="w-full"
            panelClassName="w-56"
            trigger={
              <button
                type="button"
                className={cn(
                  'flex h-[3.25rem] w-full items-center rounded-md font-medium text-muted hover:bg-surface-2 hover:text-text',
                  isExpanded
                    ? 'flex-row justify-start gap-3 px-3 text-sm'
                    : 'flex-col justify-center gap-1 px-1 text-[10px]',
                )}
              >
                <MoreHorizontal className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                <span className="truncate">{t('nav.more')}</span>
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

        <div
          role="separator"
          aria-label="Resize workspace navigation"
          aria-orientation="vertical"
          aria-valuemin={MIN_RAIL_WIDTH}
          aria-valuemax={MAX_RAIL_WIDTH}
          aria-valuenow={railWidth}
          tabIndex={0}
          title="Drag to resize · double-click or press Enter to reset"
          onPointerDown={beginResize}
          onKeyDown={resizeWithKeyboard}
          onDoubleClick={() => setRailWidth(DEFAULT_RAIL_WIDTH)}
          className="group absolute inset-y-0 -right-1 z-20 w-2 cursor-col-resize touch-none outline-none"
        >
          <span
            className={cn(
              'pointer-events-none absolute inset-y-0 left-1/2 w-px -translate-x-1/2 bg-border transition-[width,background-color] duration-150',
              'group-hover:w-0.5 group-hover:bg-accent/60 group-focus-visible:w-0.5 group-focus-visible:bg-accent',
              isResizing && 'w-0.5 bg-accent',
            )}
          />
          <span
            aria-hidden="true"
            className={cn(
              'pointer-events-none absolute left-1/2 top-1/2 h-10 w-1 -translate-x-1/2 -translate-y-1/2 rounded-full bg-border-strong opacity-40 transition-opacity',
              'group-hover:opacity-100 group-focus-visible:opacity-100',
              isResizing && 'bg-accent opacity-100',
            )}
          />
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
