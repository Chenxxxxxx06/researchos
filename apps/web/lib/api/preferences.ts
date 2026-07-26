/**
 * User-preferences API client (partition: frontend-paper).
 *
 * Real backend contract (researchos/preferences/{router,schemas}.py) per
 * CONSOLIDATION §5:
 *   GET  /users/me/preferences → { effective, global }  (consumers read `.effective`)
 *   PUT  /users/me/preferences → FULL REPLACE of the global row
 *        { theme, language, figure_style_slug, extra }  (null = "no opinion")
 *
 * Because PUT is a full replace, `updateMyPreferences` reads the stored global
 * row, merges the patch client-side, then writes the merged payload — so writing
 * `figure_style_slug` never clobbers a stored `theme`/`language` (and vice-versa).
 *
 * The backend `language` vocabulary is 'en' | 'zh-CN' while the frontend Locale
 * is 'en-US' | 'zh-CN' — map at this boundary only.
 */

import { apiRequest } from './client';
import type { Locale } from '@/lib/i18n';

export type ThemePreference = 'system' | 'light' | 'dark';
export type PreferenceLanguage = 'en' | 'zh-CN';
export type PrefExtraValue = string | number | boolean;

/** One scope's stored row; `null` = no opinion at this scope. */
export interface PreferencesPayload {
  theme: ThemePreference | null;
  language: PreferenceLanguage | null;
  figure_style_slug: string | null;
  extra: Record<string, PrefExtraValue>;
}

export interface EffectivePreferences {
  theme: ThemePreference;
  language: PreferenceLanguage;
  figure_style_slug: string;
  extra: Record<string, PrefExtraValue>;
}

export interface UserPreferences {
  effective: EffectivePreferences;
  global: PreferencesPayload | null;
}

const ENDPOINT = '/users/me/preferences';

export function localeToLanguage(locale: Locale): PreferenceLanguage {
  return locale === 'en-US' ? 'en' : 'zh-CN';
}

export function languageToLocale(language: PreferenceLanguage): Locale {
  return language === 'en' ? 'en-US' : 'zh-CN';
}

export const getMyPreferences = (): Promise<UserPreferences> =>
  apiRequest<UserPreferences>(ENDPOINT);

/**
 * Merge `patch` into the stored global row and PUT the full replacement.
 * Returns the updated envelope so callers can update their cache.
 */
export async function updateMyPreferences(
  patch: Partial<PreferencesPayload>,
): Promise<UserPreferences> {
  const current = await apiRequest<UserPreferences>(ENDPOINT);
  const stored = current.global;
  const body: PreferencesPayload = {
    theme: patch.theme !== undefined ? patch.theme : (stored?.theme ?? null),
    language: patch.language !== undefined ? patch.language : (stored?.language ?? null),
    figure_style_slug:
      patch.figure_style_slug !== undefined
        ? patch.figure_style_slug
        : (stored?.figure_style_slug ?? null),
    extra: { ...(stored?.extra ?? {}), ...(patch.extra ?? {}) },
  };
  return apiRequest<UserPreferences>(ENDPOINT, { method: 'PUT', body });
}
