/**
 * Best-effort client for the user preferences API.
 *
 * Real backend contract (researchos/preferences/{router,schemas}.py):
 *   GET  /users/me/preferences → {"effective": {...}, "global": {...}|null}
 *   PUT  /users/me/preferences → FULL REPLACE of the global row
 *        body: {theme, language, figure_style_slug, extra} (null = no opinion)
 *
 * Because PUT is a full replace, `savePreferences` first reads the stored
 * global row, merges the patch client-side, then writes the merged payload.
 *
 * Every call here is fire-and-forget: 401/404/network failures are swallowed.
 * localStorage remains the authoritative store on-device; the server only
 * carries preferences to fresh browsers (sync-down in lib/theme/index.tsx).
 *
 * NOTE: the backend `language` vocabulary is 'en' | 'zh-CN' while the
 * frontend Locale is 'en-US' | 'zh-CN' — map at this boundary only.
 */

import { apiRequest } from '@/lib/api/client';
import type { Locale } from '@/lib/i18n';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

/** Backend language vocabulary (differs from the frontend Locale). */
export type PreferenceLanguage = 'en' | 'zh-CN';

type ExtraValue = string | number | boolean;

/** One scope's stored row; `null` = no opinion at this scope. */
export interface PreferencesPayload {
  theme: ThemePreference | null;
  language: PreferenceLanguage | null;
  figure_style_slug: string | null;
  extra: Record<string, ExtraValue>;
}

export interface EffectivePreferences {
  theme: ThemePreference;
  language: PreferenceLanguage;
  figure_style_slug: string;
  extra: Record<string, ExtraValue>;
}

export interface UserPreferencesResponse {
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

/** Read server preferences; `null` on any failure (endpoint absent, 401, …). */
export async function fetchPreferences(): Promise<UserPreferencesResponse | null> {
  try {
    return await apiRequest<UserPreferencesResponse>(ENDPOINT);
  } catch {
    return null;
  }
}

/**
 * Merge `patch` into the stored global row and PUT the full replacement.
 * Fire-and-forget: never throws, never surfaces errors to the UI.
 */
export async function savePreferences(patch: Partial<PreferencesPayload>): Promise<void> {
  try {
    const current = await apiRequest<UserPreferencesResponse>(ENDPOINT);
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
    await apiRequest<UserPreferencesResponse>(ENDPOINT, { method: 'PUT', body });
  } catch {
    // localStorage is authoritative on-device; server sync is best-effort.
  }
}
