'use client';

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';

import { enUS } from './dictionaries/en-US';
import { zhCN, type DictKey } from './dictionaries/zh-CN';

export type Locale = 'zh-CN' | 'en-US';

const DICTS: Record<Locale, Record<DictKey, string>> = {
  'zh-CN': zhCN,
  'en-US': enUS,
};

const STORAGE_KEY = 'ros_locale';
const DEFAULT_LOCALE: Locale = 'zh-CN';

interface I18nContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: DictKey) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(DEFAULT_LOCALE);

  useEffect(() => {
    const stored = window.localStorage.getItem(STORAGE_KEY) as Locale | null;
    if (stored === 'zh-CN' || stored === 'en-US') setLocaleState(stored);
  }, []);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    window.localStorage.setItem(STORAGE_KEY, next);
    document.documentElement.lang = next;
  }, []);

  const t = useCallback((key: DictKey) => DICTS[locale][key] ?? key, [locale]);

  return <I18nContext.Provider value={{ locale, setLocale, t }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}

export type { DictKey };
