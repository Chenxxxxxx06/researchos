/**
 * Pure word-level diff (partition: frontend-paper, Design B.6).
 *
 * Tokenizes on whitespace runs (separators kept) and computes an LCS via DP,
 * capped at 400×400 tokens; beyond the cap it degrades to a single whole-block
 * delete+insert pair. Server-side suggestions usually carry pre-computed `spans`;
 * this is the fallback when they are absent and for the assistant insert preview.
 */

export type WordDiffKind = 'same' | 'del' | 'ins';

export interface WordDiffSegment {
  kind: WordDiffKind;
  text: string;
}

const MAX_TOKENS = 400;

/** Split into alternating word/separator tokens (separators preserved). */
export function tokenize(input: string): string[] {
  if (input === '') return [];
  return input.split(/(\s+)/).filter((tok) => tok !== '');
}

export function wordDiff(a: string, b: string): WordDiffSegment[] {
  const aTok = tokenize(a);
  const bTok = tokenize(b);

  if (aTok.length === 0 && bTok.length === 0) return [];
  if (aTok.length === 0) return [{ kind: 'ins', text: b }];
  if (bTok.length === 0) return [{ kind: 'del', text: a }];

  // Guardrail: quadratic DP is capped; larger inputs get a coarse block diff.
  if (aTok.length > MAX_TOKENS || bTok.length > MAX_TOKENS) {
    return [
      { kind: 'del', text: a },
      { kind: 'ins', text: b },
    ];
  }

  const n = aTok.length;
  const m = bTok.length;
  // dp[i][j] = LCS length of aTok[i:] and bTok[j:].
  const dp: number[][] = Array.from({ length: n + 1 }, () => new Array<number>(m + 1).fill(0));
  for (let i = n - 1; i >= 0; i--) {
    for (let j = m - 1; j >= 0; j--) {
      dp[i][j] = aTok[i] === bTok[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const out: WordDiffSegment[] = [];
  const push = (kind: WordDiffKind, text: string) => {
    const last = out[out.length - 1];
    if (last && last.kind === kind) last.text += text;
    else out.push({ kind, text });
  };

  let i = 0;
  let j = 0;
  while (i < n && j < m) {
    if (aTok[i] === bTok[j]) {
      push('same', aTok[i]);
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      push('del', aTok[i]);
      i++;
    } else {
      push('ins', bTok[j]);
      j++;
    }
  }
  while (i < n) push('del', aTok[i++]);
  while (j < m) push('ins', bTok[j++]);
  return out;
}
