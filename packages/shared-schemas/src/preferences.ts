/**
 * User preference REST contracts (CONSOLIDATION §5).
 *
 * Mirrors apps/api/researchos/preferences/schemas.py. GET/PUT
 * /users/me/preferences; PUT is a full replace of the global row. Consumers
 * read `.effective` and merge client-side before PUT. Field names are
 * `language` (not locale) and `figure_style_slug` (not default_figure_style).
 */

export type ThemePreference = 'system' | 'light' | 'dark';
export type LanguagePreference = 'en' | 'zh-CN';

export type PreferenceExtraValue = string | number | boolean;

/** One scope's stored row (PUT body and scope echo). null = no opinion. */
export interface UserPreferences {
  theme: ThemePreference | null;
  language: LanguagePreference | null;
  figure_style_slug: string | null;
  /** Flat forward-compatible bucket for frontend-only settings (8 KB cap). */
  extra: Record<string, PreferenceExtraValue>;
}

/** Fully-resolved preferences (project -> global -> defaults). */
export interface EffectivePreferences {
  theme: ThemePreference;
  language: LanguagePreference;
  figure_style_slug: string;
  extra: Record<string, PreferenceExtraValue>;
}

/** GET/PUT /users/me/preferences response. */
export interface PreferencesResponse {
  effective: EffectivePreferences;
  global: UserPreferences | null;
}

/** GET/PUT /projects/{id}/preferences response. */
export interface ProjectPreferencesResponse {
  effective: EffectivePreferences;
  project: UserPreferences | null;
  global: UserPreferences | null;
}
