'use client';

import { useQuery } from '@tanstack/react-query';

import { citationKey, listPapers, type Page, type Paper } from '@/lib/api/papers';

/** A citation carried on an agent-run completion payload (live runs). */
export interface CitationPayload {
  source: string;
  external_id: string;
  title?: string;
  url?: string;
}

export interface LibraryHit {
  paperId: string;
  title: string;
}

export type LibraryMap = Map<string, LibraryHit>;

/** Resolved chip model — the honest three-state citation ladder (D7.4). */
export type CitationChipModel =
  | { state: 'in-library'; key: string; title: string; paperId: string }
  | { state: 'external'; key: string; title: string; url?: string }
  | { state: 'unverified'; key: string };

/** Split a `source:external_id` key on its FIRST colon (ids may contain colons). */
export function parseCitationKey(key: string): { source: string; external_id: string } | null {
  const idx = key.indexOf(':');
  if (idx <= 0 || idx === key.length - 1) return null;
  return { source: key.slice(0, idx), external_id: key.slice(idx + 1) };
}

/**
 * Build a `source:external_id → {paperId, title}` map from the library query
 * cache. Shares the `['papers', projectId]` key so it never triggers an extra
 * fetch; `select` is memoized by TanStack so the Map is referentially stable.
 */
export function useCitationResolver(projectId: string): LibraryMap {
  const { data } = useQuery({
    queryKey: ['papers', projectId],
    queryFn: () => listPapers(projectId, { limit: 100 }),
    select: (page: Page<Paper>): LibraryMap => {
      const map: LibraryMap = new Map();
      for (const p of page.items) {
        map.set(citationKey(p.source, p.external_id), { paperId: p.id, title: p.title });
      }
      return map;
    },
  });
  return data ?? EMPTY_MAP;
}

const EMPTY_MAP: LibraryMap = new Map();

/**
 * Resolve one citation key through the ladder:
 *   (a) in the library map      → verified-in-library (links to the Reading Room)
 *   (b) payload carries title/url → verified-external (links out)
 *   (c) key only, unresolvable   → unverified
 */
export function resolveCitation(
  key: string,
  payload: CitationPayload[],
  library: LibraryMap,
): CitationChipModel {
  const inLib = library.get(key);
  if (inLib) return { state: 'in-library', key, title: inLib.title, paperId: inLib.paperId };

  const match = payload.find((c) => citationKey(c.source, c.external_id) === key);
  if (match && (match.title || match.url)) {
    return { state: 'external', key, title: match.title ?? key, url: match.url };
  }
  return { state: 'unverified', key };
}

/** Convenience: PaperCitation objects → `CitationPayload[]` (identity-shaped). */
export function toPayload(
  citations: readonly { source: string; external_id: string; title?: string; url?: string }[],
): CitationPayload[] {
  return citations.map((c) => ({
    source: c.source,
    external_id: c.external_id,
    title: c.title,
    url: c.url,
  }));
}
