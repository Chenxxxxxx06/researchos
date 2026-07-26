/**
 * Inline before/after diff for tracked-changes UX and patch summaries.
 * LCS over word (or char) tokens with an O(n·m) budget guard.
 */

import { cn } from '@/lib/utils';

export type DiffMode = 'words' | 'chars';

export interface DiffRun {
  kind: 'equal' | 'del' | 'ins';
  text: string;
}

/** DP cell budget: past this the LCS table is too big — fall back wholesale. */
const LCS_BUDGET = 250_000;

function tokenize(text: string, mode: DiffMode): string[] {
  if (mode === 'chars') return Array.from(text);
  // Words + whitespace preserved so runs re-join losslessly.
  return text.split(/(\s+)/).filter((t) => t.length > 0);
}

function pushRun(runs: DiffRun[], kind: DiffRun['kind'], text: string): void {
  const last = runs[runs.length - 1];
  if (last && last.kind === kind) last.text += text;
  else runs.push({ kind, text });
}

/**
 * Compute equal/del/ins runs between two strings. Exported for unit tests.
 * Over the budget (`tokens(before) × tokens(after) > 250k`) returns the
 * wholesale fallback `[del(before), ins(after)]`.
 */
export function diffRuns(before: string, after: string, mode: DiffMode = 'words'): DiffRun[] {
  if (before === after) return before.length > 0 ? [{ kind: 'equal', text: before }] : [];
  const a = tokenize(before, mode);
  const b = tokenize(after, mode);
  if (a.length * b.length > LCS_BUDGET) {
    const runs: DiffRun[] = [];
    if (before.length > 0) runs.push({ kind: 'del', text: before });
    if (after.length > 0) runs.push({ kind: 'ins', text: after });
    return runs;
  }

  // LCS length table (n+1 × m+1), then backtrack.
  const n = a.length;
  const m = b.length;
  const dp: Uint32Array[] = Array.from({ length: n + 1 }, () => new Uint32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i]![j] =
        a[i] === b[j] ? dp[i + 1]![j + 1]! + 1 : Math.max(dp[i + 1]![j]!, dp[i]![j + 1]!);
    }
  }

  const runs: DiffRun[] = [];
  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (a[i] === b[j]) {
      pushRun(runs, 'equal', a[i]!);
      i++;
      j++;
    } else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) {
      pushRun(runs, 'del', a[i]!);
      i++;
    } else {
      pushRun(runs, 'ins', b[j]!);
      j++;
    }
  }
  while (i < n) {
    pushRun(runs, 'del', a[i]!);
    i++;
  }
  while (j < m) {
    pushRun(runs, 'ins', b[j]!);
    j++;
  }
  return runs;
}

export interface DiffTextProps {
  before: string;
  after: string;
  mode?: DiffMode;
  className?: string;
}

/** Renders native <del>/<ins> so screen readers announce the change semantics. */
export function DiffText({ before, after, mode = 'words', className }: DiffTextProps) {
  const runs = diffRuns(before, after, mode);
  return (
    <span className={cn('whitespace-pre-wrap', className)}>
      {runs.map((run, index) => {
        if (run.kind === 'del') {
          return (
            <del
              key={index}
              className="rounded-sm bg-danger-bg text-danger line-through decoration-danger/50"
            >
              {run.text}
            </del>
          );
        }
        if (run.kind === 'ins') {
          return (
            <ins key={index} className="rounded-sm bg-success-bg text-success no-underline">
              {run.text}
            </ins>
          );
        }
        return <span key={index}>{run.text}</span>;
      })}
    </span>
  );
}
