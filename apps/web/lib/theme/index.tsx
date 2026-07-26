'use client';

/**
 * Theme engine: light / dark / system with FOUC-free boot.
 *
 * - The inline script in app/layout.tsx stamps `data-theme` on <html> before
 *   first paint from localStorage (`ros-theme`); this provider takes over on
 *   the client and keeps the attribute, localStorage, and context in sync.
 * - Preference changes are pushed to the server best-effort (localStorage is
 *   authoritative on-device); fresh browsers with no local entry adopt the
 *   server's stored preference once (sync-down, without persisting locally).
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from 'react';

import { useI18n } from '@/lib/i18n';
import {
  fetchPreferences,
  languageToLocale,
  savePreferences,
  type ResolvedTheme,
  type ThemePreference,
} from './preferences';

export type { ResolvedTheme, ThemePreference };

export const THEME_STORAGE_KEY = 'ros-theme';
const LOCALE_STORAGE_KEY = 'ros_locale';

interface ThemeContextValue {
  /** The stored preference (absent localStorage entry = 'system'). */
  preference: ThemePreference;
  /** What is actually applied to <html data-theme>. */
  resolved: ResolvedTheme;
  setTheme: (preference: ThemePreference) => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

function isPreference(value: unknown): value is ThemePreference {
  return value === 'light' || value === 'dark' || value === 'system';
}

function systemTheme(): ResolvedTheme {
  if (typeof window === 'undefined') return 'light';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function resolve(preference: ThemePreference): ResolvedTheme {
  return preference === 'system' ? systemTheme() : preference;
}

function stamp(resolved: ResolvedTheme): void {
  document.documentElement.dataset.theme = resolved;
}

function readStoredPreference(): ThemePreference | null {
  if (typeof window === 'undefined') return null;
  try {
    const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isPreference(stored) ? stored : null;
  } catch {
    return null;
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { setLocale } = useI18n();
  // Hydration-safe: first client render matches SSR ('system'/'light'); the
  // mount effect below adopts the real values. The PAGE theme never flashes —
  // colors are driven by the data-theme attribute the boot script stamped.
  const [preference, setPreference] = useState<ThemePreference>('system');
  const [resolved, setResolved] = useState<ResolvedTheme>('light');

  useEffect(() => {
    setPreference(readStoredPreference() ?? 'system');
    // The boot script already resolved and stamped the theme pre-paint.
    setResolved(document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light');
  }, []);

  const apply = useCallback((next: ThemePreference) => {
    const nextResolved = resolve(next);
    stamp(nextResolved);
    setPreference(next);
    setResolved(nextResolved);
  }, []);

  const setTheme = useCallback(
    (next: ThemePreference) => {
      apply(next);
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        // Private mode etc. — in-memory state still applies for this session.
      }
      void savePreferences({ theme: next });
    },
    [apply],
  );

  // Follow OS changes live while the preference is 'system'.
  useEffect(() => {
    if (preference !== 'system') return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const onChange = () => {
      const next = media.matches ? 'dark' : 'light';
      stamp(next);
      setResolved(next);
    };
    media.addEventListener('change', onChange);
    return () => media.removeEventListener('change', onChange);
  }, [preference]);

  // Sync-down: a fresh browser (no explicit local entry) adopts the server's
  // stored preference. Device-local explicit choices always win; adopted
  // values are NOT persisted locally so the server keeps carrying them.
  const syncedDown = useRef(false);
  useEffect(() => {
    if (syncedDown.current) return;
    syncedDown.current = true;
    const hasLocalTheme = readStoredPreference() !== null;
    let hasLocalLocale = true;
    try {
      const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
      hasLocalLocale = stored === 'zh-CN' || stored === 'en-US';
    } catch {
      // Treat unreadable storage as "has a choice" — do not override.
    }
    if (hasLocalTheme && hasLocalLocale) return;
    void fetchPreferences().then((prefs) => {
      if (!prefs) return;
      if (!hasLocalTheme && prefs.global?.theme && isPreference(prefs.global.theme)) {
        apply(prefs.global.theme);
      }
      if (!hasLocalLocale && prefs.global?.language) {
        setLocale(languageToLocale(prefs.global.language));
      }
    });
  }, [apply, setLocale]);

  return (
    <ThemeContext.Provider value={{ preference, resolved, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used within ThemeProvider');
  return ctx;
}
