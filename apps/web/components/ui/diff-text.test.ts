import { describe, expect, it } from 'vitest';

import { diffRuns } from './diff-text';

function joined(runs: ReturnType<typeof diffRuns>, kinds: Array<'equal' | 'del' | 'ins'>) {
  return runs
    .filter((r) => kinds.includes(r.kind))
    .map((r) => r.text)
    .join('');
}

describe('diffRuns', () => {
  it('returns one equal run for identical inputs', () => {
    expect(diffRuns('same text', 'same text')).toEqual([{ kind: 'equal', text: 'same text' }]);
  });

  it('returns [] for two empty strings', () => {
    expect(diffRuns('', '')).toEqual([]);
  });

  it('emits del/ins runs around a word replacement', () => {
    const runs = diffRuns('the quick fox', 'the lazy fox');
    expect(runs.some((r) => r.kind === 'del' && r.text.includes('quick'))).toBe(true);
    expect(runs.some((r) => r.kind === 'ins' && r.text.includes('lazy'))).toBe(true);
    // Reconstruction invariants: equal+del = before, equal+ins = after.
    expect(joined(runs, ['equal', 'del'])).toBe('the quick fox');
    expect(joined(runs, ['equal', 'ins'])).toBe('the lazy fox');
  });

  it('handles pure insertion and pure deletion', () => {
    expect(diffRuns('', 'new')).toEqual([{ kind: 'ins', text: 'new' }]);
    expect(diffRuns('old', '')).toEqual([{ kind: 'del', text: 'old' }]);
  });

  it('merges adjacent runs of the same kind', () => {
    const runs = diffRuns('a b', 'x y', 'words');
    // No two consecutive runs share a kind.
    for (let i = 1; i < runs.length; i++) {
      expect(runs[i]!.kind).not.toBe(runs[i - 1]!.kind);
    }
  });

  it('supports char mode', () => {
    const runs = diffRuns('cat', 'cart', 'chars');
    expect(joined(runs, ['equal', 'del'])).toBe('cat');
    expect(joined(runs, ['equal', 'ins'])).toBe('cart');
  });

  it('falls back wholesale past the LCS budget', () => {
    // 600×600 word tokens (with whitespace ≈ 1199×1199 > 250k cells).
    const before = Array.from({ length: 600 }, (_, i) => `a${i}`).join(' ');
    const after = Array.from({ length: 600 }, (_, i) => `b${i}`).join(' ');
    const runs = diffRuns(before, after);
    expect(runs).toEqual([
      { kind: 'del', text: before },
      { kind: 'ins', text: after },
    ]);
  });
});
