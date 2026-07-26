'use client';

/**
 * Built-in commands: navigation (`g` sequences), theme, language, sign-out,
 * palette + cheatsheet toggles. Mounted once by the workspace layout;
 * re-registers when locale or project changes (titles are pre-localized).
 */

import { useParams } from 'next/navigation';
import {
  Code2,
  FileText,
  FlaskConical,
  FolderKanban,
  Hammer,
  Keyboard,
  Languages,
  LayoutDashboard,
  LogOut,
  Monitor,
  Moon,
  Puzzle,
  Search,
  Settings,
  Sun,
} from 'lucide-react';

import { logout } from '@/lib/api/auth';
import { useI18n, type DictKey } from '@/lib/i18n';
import { useTheme } from '@/lib/theme';
import { useCommandStore, useRegisterCommands, type Command } from './registry';

const PROJECT_NAV: Array<{
  id: string;
  key: DictKey;
  segment: string;
  shortcut: string;
  icon: Command['icon'];
}> = [
  { id: 'nav.overview', key: 'nav.overview', segment: 'overview', shortcut: 'g o', icon: LayoutDashboard },
  { id: 'nav.research', key: 'nav.research', segment: 'research', shortcut: 'g r', icon: Search },
  { id: 'nav.ide', key: 'nav.ide', segment: 'ide', shortcut: 'g i', icon: Code2 },
  { id: 'nav.experiments', key: 'nav.experiments', segment: 'experiments', shortcut: 'g e', icon: FlaskConical },
  { id: 'nav.paper', key: 'nav.paper', segment: 'paper', shortcut: 'g p', icon: FileText },
  { id: 'nav.skills', key: 'nav.skills', segment: 'skills', shortcut: 'g k', icon: Puzzle },
  { id: 'nav.skillBuilder', key: 'nav.skillBuilder', segment: 'skills/builder', shortcut: 'g b', icon: Hammer },
  { id: 'nav.settings', key: 'nav.settings', segment: 'settings', shortcut: 'g s', icon: Settings },
];

export function useBuiltinCommands(): void {
  const { t, locale, setLocale } = useI18n();
  const { setTheme } = useTheme();
  const params = useParams<{ projectId?: string }>();
  const projectId = params?.projectId ?? null;

  useRegisterCommands(
    () => [
      {
        id: 'nav.projects',
        title: t('nav.projects'),
        section: 'navigate',
        shortcut: 'g j',
        icon: FolderKanban,
        keywords: ['projects', 'home'],
        run: (ctx) => ctx.router.push('/projects'),
      },
      ...PROJECT_NAV.map(
        (item): Command => ({
          id: item.id,
          title: t(item.key),
          section: 'navigate',
          shortcut: item.shortcut,
          icon: item.icon,
          keywords: [item.segment],
          enabled: (ctx) => Boolean(ctx.projectId),
          run: (ctx) => {
            if (ctx.projectId) ctx.router.push(`/projects/${ctx.projectId}/${item.segment}`);
          },
        }),
      ),
      {
        id: 'palette.open',
        title: t('palette.hint'),
        section: 'action',
        shortcut: 'mod+k',
        icon: Search,
        keywords: ['command', 'palette', 'search'],
        run: () => {
          const store = useCommandStore.getState();
          store.setOpen(!store.open);
        },
      },
      {
        id: 'shortcuts.help',
        title: t('shortcuts.help'),
        section: 'action',
        shortcut: '?',
        icon: Keyboard,
        keywords: ['shortcuts', 'keyboard', 'help'],
        run: () => useCommandStore.getState().setCheatsheetOpen(true),
      },
      {
        id: 'action.switch-language',
        title: t('palette.switchLanguage'),
        section: 'action',
        icon: Languages,
        keywords: ['language', 'locale', 'english', 'chinese', '中文'],
        run: () => setLocale(locale === 'zh-CN' ? 'en-US' : 'zh-CN'),
      },
      {
        id: 'action.sign-out',
        title: t('common.signOut'),
        section: 'action',
        icon: LogOut,
        keywords: ['logout', 'sign out'],
        run: async (ctx) => {
          try {
            await logout();
          } finally {
            ctx.queryClient.clear();
            ctx.router.push('/login');
          }
        },
      },
      {
        id: 'theme.light',
        title: `${t('theme.label')}: ${t('theme.light')}`,
        section: 'theme',
        icon: Sun,
        keywords: ['theme', 'light'],
        run: () => setTheme('light'),
      },
      {
        id: 'theme.dark',
        title: `${t('theme.label')}: ${t('theme.dark')}`,
        section: 'theme',
        icon: Moon,
        keywords: ['theme', 'dark'],
        run: () => setTheme('dark'),
      },
      {
        id: 'theme.system',
        title: `${t('theme.label')}: ${t('theme.system')}`,
        section: 'theme',
        icon: Monitor,
        keywords: ['theme', 'system', 'auto'],
        run: () => setTheme('system'),
      },
    ],
    [t, locale, setLocale, setTheme, projectId],
  );
}
