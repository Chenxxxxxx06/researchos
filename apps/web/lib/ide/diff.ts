/**
 * Dependency-free line diff (D4). Myers O(ND) greedy diff on line arrays plus
 * hunk grouping and unified-hunk parsing. Pure functions, no DOM, no runtime
 * imports (type-only import of the patch shapes is allowed).
 *
 * Correctness is exercised indirectly by the IDE Playwright spec (a known patch
 * produces known +/- counts).
 */

import type { PatchFile, PatchHunk } from '@/lib/api/patches';

export interface DiffLine {
  kind: 'ctx' | 'add' | 'del';
  oldNo: number | null;
  newNo: number | null;
  text: string;
}

export interface DisplayHunk {
  header: string;
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  lines: DiffLine[];
}

/** Beyond this, callers should defer to Monaco ("diff too large"). */
export const MAX_DIFF_LINES = 20_000;

function countLines(s: string): number {
  if (s === '') return 0;
  let n = 1;
  for (let i = 0; i < s.length; i++) if (s.charCodeAt(i) === 10) n++;
  return n;
}

export function diffTooLarge(base: string, next: string): boolean {
  return countLines(base) > MAX_DIFF_LINES || countLines(next) > MAX_DIFF_LINES;
}

function splitLines(s: string): string[] {
  if (s === '') return [];
  const lines = s.split('\n');
  if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();
  return lines;
}

/**
 * Myers greedy diff with a trace, backtracked into a flat DiffLine[] (context,
 * additions, deletions in original order).
 */
export function diffLines(base: string, next: string): DiffLine[] {
  const a = splitLines(base);
  const b = splitLines(next);
  const n = a.length;
  const m = b.length;

  if (n === 0 && m === 0) return [];
  if (n === 0) return b.map((text, i) => ({ kind: 'add', oldNo: null, newNo: i + 1, text }));
  if (m === 0) return a.map((text, i) => ({ kind: 'del', oldNo: i + 1, newNo: null, text }));

  const max = n + m;
  const offset = max;
  const v = new Array<number>(2 * max + 1).fill(0);
  const trace: number[][] = [];
  let found = -1;

  outer: for (let d = 0; d <= max; d++) {
    trace.push(v.slice());
    for (let k = -d; k <= d; k += 2) {
      let x: number;
      if (k === -d || (k !== d && v[offset + k - 1] < v[offset + k + 1])) {
        x = v[offset + k + 1]; // down = insertion
      } else {
        x = v[offset + k - 1] + 1; // right = deletion
      }
      let y = x - k;
      while (x < n && y < m && a[x] === b[y]) {
        x++;
        y++;
      }
      v[offset + k] = x;
      if (x >= n && y >= m) {
        found = d;
        break outer;
      }
    }
  }

  const out: DiffLine[] = [];
  let x = n;
  let y = m;
  for (let d = found; d > 0; d--) {
    const vv = trace[d];
    const k = x - y;
    let prevK: number;
    if (k === -d || (k !== d && vv[offset + k - 1] < vv[offset + k + 1])) {
      prevK = k + 1;
    } else {
      prevK = k - 1;
    }
    const prevX = vv[offset + prevK];
    const prevY = prevX - prevK;
    while (x > prevX && y > prevY) {
      out.push({ kind: 'ctx', oldNo: x, newNo: y, text: a[x - 1] });
      x--;
      y--;
    }
    if (x === prevX) {
      out.push({ kind: 'add', oldNo: null, newNo: y, text: b[y - 1] });
      y--;
    } else {
      out.push({ kind: 'del', oldNo: x, newNo: null, text: a[x - 1] });
      x--;
    }
  }
  while (x > 0 && y > 0) {
    out.push({ kind: 'ctx', oldNo: x, newNo: y, text: a[x - 1] });
    x--;
    y--;
  }
  while (x > 0) {
    out.push({ kind: 'del', oldNo: x, newNo: null, text: a[x - 1] });
    x--;
  }
  while (y > 0) {
    out.push({ kind: 'add', oldNo: null, newNo: y, text: b[y - 1] });
    y--;
  }
  out.reverse();
  return out;
}

export function diffStats(lines: DiffLine[]): { additions: number; deletions: number } {
  let additions = 0;
  let deletions = 0;
  for (const l of lines) {
    if (l.kind === 'add') additions++;
    else if (l.kind === 'del') deletions++;
  }
  return { additions, deletions };
}

/** Group a flat DiffLine[] into hunks with `context` lines of surrounding context. */
export function groupHunks(lines: DiffLine[], context = 3): DisplayHunk[] {
  const changed: number[] = [];
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].kind !== 'ctx') changed.push(i);
  }
  if (changed.length === 0) return [];

  // Cluster changed indices whose context windows touch (gap <= 2*context).
  const clusters: Array<[number, number]> = [];
  let clusterStart = changed[0];
  let prev = changed[0];
  for (let i = 1; i < changed.length; i++) {
    if (changed[i] - prev > context * 2) {
      clusters.push([clusterStart, prev]);
      clusterStart = changed[i];
    }
    prev = changed[i];
  }
  clusters.push([clusterStart, prev]);

  return clusters.map(([firstChange, lastChange]) => {
    const start = Math.max(0, firstChange - context);
    const end = Math.min(lines.length - 1, lastChange + context);
    const hunkLines = lines.slice(start, end + 1);
    const firstOld = hunkLines.find((l) => l.oldNo != null);
    const firstNew = hunkLines.find((l) => l.newNo != null);
    let oldLines = 0;
    let newLines = 0;
    for (const l of hunkLines) {
      if (l.oldNo != null) oldLines++;
      if (l.newNo != null) newLines++;
    }
    const oldStart = firstOld?.oldNo ?? 0;
    const newStart = firstNew?.newNo ?? 0;
    return {
      header: `@@ -${oldStart},${oldLines} +${newStart},${newLines} @@`,
      oldStart,
      oldLines,
      newStart,
      newLines,
      lines: hunkLines,
    };
  });
}

/** Parse server-provided unified hunks into display rows. */
export function toDisplayHunks(serverHunks: PatchHunk[]): DisplayHunk[] {
  return serverHunks.map((h) => {
    const lines: DiffLine[] = [];
    let oldNo = h.old_start;
    let newNo = h.new_start;
    const body = h.content.split('\n');
    if (body.length > 0 && body[body.length - 1] === '') body.pop();
    for (const raw of body) {
      if (raw.startsWith('@@')) continue;
      if (raw.startsWith('\\')) continue; // "\ No newline at end of file"
      const marker = raw[0] ?? ' ';
      const text = raw.slice(1);
      if (marker === '+') {
        lines.push({ kind: 'add', oldNo: null, newNo, text });
        newNo++;
      } else if (marker === '-') {
        lines.push({ kind: 'del', oldNo, newNo: null, text });
        oldNo++;
      } else {
        lines.push({ kind: 'ctx', oldNo, newNo, text });
        oldNo++;
        newNo++;
      }
    }
    return {
      header: h.header,
      oldStart: h.old_start,
      oldLines: h.old_lines,
      newStart: h.new_start,
      newLines: h.new_lines,
      lines,
    };
  });
}

function wholeFileHunk(content: string, kind: 'add' | 'del'): DisplayHunk[] {
  const rows = splitLines(content);
  if (rows.length === 0) return [];
  const lines: DiffLine[] = rows.map((text, i) =>
    kind === 'add'
      ? { kind: 'add', oldNo: null, newNo: i + 1, text }
      : { kind: 'del', oldNo: i + 1, newNo: null, text },
  );
  return [
    {
      header: kind === 'add' ? `@@ -0,0 +1,${rows.length} @@` : `@@ -1,${rows.length} +0,0 @@`,
      oldStart: kind === 'add' ? 0 : 1,
      oldLines: kind === 'add' ? 0 : rows.length,
      newStart: kind === 'add' ? 1 : 0,
      newLines: kind === 'add' ? rows.length : 0,
      lines,
    },
  ];
}

export type FileDiffSource = 'computed' | 'server' | 'whole';

export interface FileDiffModel {
  hunks: DisplayHunk[];
  additions: number;
  deletions: number;
  source: FileDiffSource;
  tooLarge: boolean;
  /** Base/modified strings for the "open full diff" Monaco takeover. */
  base: string;
  modified: string;
}

/**
 * Resolve the display diff for a patch file (D3.4). Order: recorded
 * `base_content` (client-computed) → server hunks → whole-file. Never diffs the
 * live file.
 */
export function resolveFileHunks(file: PatchFile): FileDiffModel {
  const base = file.base_content ?? '';
  const modified = file.new_content ?? '';

  // (a) recorded base present → client-computed diff.
  if (file.base_content != null) {
    if (diffTooLarge(base, modified)) {
      return { hunks: [], additions: 0, deletions: 0, source: 'computed', tooLarge: true, base, modified };
    }
    const lines = diffLines(base, modified);
    const { additions, deletions } = diffStats(lines);
    return { hunks: groupHunks(lines), additions, deletions, source: 'computed', tooLarge: false, base, modified };
  }

  // (b) server hunks present → render verbatim.
  if (file.hunks.length > 0) {
    const hunks = toDisplayHunks(file.hunks);
    let additions = 0;
    let deletions = 0;
    for (const h of hunks) {
      const s = diffStats(h.lines);
      additions += s.additions;
      deletions += s.deletions;
    }
    return { hunks, additions, deletions, source: 'server', tooLarge: false, base, modified };
  }

  // (c) create/delete/legacy → whole-file add or remove.
  const kind = file.change_type === 'delete' ? 'del' : 'add';
  const content = kind === 'del' ? base : modified;
  const hunks = wholeFileHunk(content, kind);
  const { additions, deletions } = hunks.length ? diffStats(hunks[0].lines) : { additions: 0, deletions: 0 };
  return { hunks, additions, deletions, source: 'whole', tooLarge: false, base, modified };
}
