/**
 * Case-insensitive subsequence fuzzy scorer for the command palette.
 * Pure module — unit-tested in node.
 *
 * score = 100
 *       + 20 · (match starts at index 0)
 *       + 10 · (count of matches at word boundaries)
 *       −  1 · (gap count: non-contiguous breaks between matched chars)
 *       − 0.1 · target.length
 * Returns null when `query` is not a subsequence of `target`.
 */

const BOUNDARY = /[\s\-_./:]/;

export function fuzzyScore(query: string, target: string): number | null {
  const q = query.toLowerCase();
  const t = target.toLowerCase();
  if (q.length === 0) return 100 - 0.1 * target.length;
  if (q.length > t.length) return null;

  let boundaryMatches = 0;
  let gaps = 0;
  let firstMatch = -1;
  let prevMatch = -2;
  let ti = 0;

  for (let qi = 0; qi < q.length; qi++) {
    const ch = q[qi]!;
    let found = -1;
    while (ti < t.length) {
      if (t[ti] === ch) {
        found = ti;
        break;
      }
      ti++;
    }
    if (found === -1) return null;
    if (firstMatch === -1) firstMatch = found;
    if (prevMatch >= 0 && found !== prevMatch + 1) gaps++;
    if (found === 0 || BOUNDARY.test(t[found - 1]!)) boundaryMatches++;
    prevMatch = found;
    ti = found + 1;
  }

  return (
    100 +
    (firstMatch === 0 ? 20 : 0) +
    10 * boundaryMatches -
    1 * gaps -
    0.1 * target.length
  );
}

/**
 * Score a command: max over its title and keywords (keywords scored ×0.9).
 * Null when nothing matches.
 */
export function commandScore(
  query: string,
  cmd: { title: string; keywords?: string[] },
): number | null {
  let best: number | null = fuzzyScore(query, cmd.title);
  for (const keyword of cmd.keywords ?? []) {
    const s = fuzzyScore(query, keyword);
    if (s !== null) {
      const weighted = s * 0.9;
      if (best === null || weighted > best) best = weighted;
    }
  }
  return best;
}
