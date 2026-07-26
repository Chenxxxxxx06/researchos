/**
 * localStorage draft autosave (partition: frontend-paper, Design A.3).
 *
 * A crash never loses more than one debounce interval of work. Keyed per
 * `{latexProjectId}:{path}`; a separate `:conflict-backup` slot preserves local
 * text when the user takes the server version in a merge.
 */

export interface PaperDraft {
  baseVersion: number;
  content: string;
  savedAt: number;
}

const PREFIX = 'ros-paper-draft';

const key = (lid: string, path: string, suffix = ''): string =>
  `${PREFIX}:${lid}:${path}${suffix}`;

function canUseStorage(): boolean {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined';
}

export function writeDraft(lid: string, path: string, draft: PaperDraft): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(key(lid, path), JSON.stringify(draft));
  } catch {
    // Quota/private-mode — drafts are best-effort.
  }
}

export function readDraft(lid: string, path: string): PaperDraft | null {
  if (!canUseStorage()) return null;
  try {
    const raw = window.localStorage.getItem(key(lid, path));
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PaperDraft;
    if (typeof parsed.content !== 'string' || typeof parsed.baseVersion !== 'number') return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearDraft(lid: string, path: string): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.removeItem(key(lid, path));
  } catch {
    // ignore
  }
}

/** Preserve local text under the conflict-backup slot before taking the server copy. */
export function writeConflictBackup(lid: string, path: string, content: string): void {
  if (!canUseStorage()) return;
  try {
    window.localStorage.setItem(
      key(lid, path, ':conflict-backup'),
      JSON.stringify({ baseVersion: 0, content, savedAt: Date.now() } satisfies PaperDraft),
    );
  } catch {
    // ignore
  }
}
