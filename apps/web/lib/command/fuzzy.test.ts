import { describe, expect, it } from 'vitest';

import { commandScore, fuzzyScore } from './fuzzy';

describe('fuzzyScore', () => {
  it('returns null when query is not a subsequence', () => {
    expect(fuzzyScore('xyz', 'open ide')).toBeNull();
    expect(fuzzyScore('ideq', 'ide')).toBeNull();
  });

  it('matches subsequences case-insensitively', () => {
    expect(fuzzyScore('ide', 'AI IDE')).not.toBeNull();
    expect(fuzzyScore('OI', 'open ide')).not.toBeNull();
  });

  it('gives the prefix bonus for matches starting at index 0', () => {
    const prefix = fuzzyScore('ide', 'ide panel')!;
    const nonPrefix = fuzzyScore('ide', 'the ide panel')!;
    expect(prefix).toBeGreaterThan(nonPrefix);
  });

  it('rewards word-boundary matches', () => {
    // 'op' at the start of two words vs buried inside one word.
    const boundary = fuzzyScore('op', 'open panel')!;
    const buried = fuzzyScore('op', 'chopchop')!;
    expect(boundary).toBeGreaterThan(buried);
  });

  it('penalizes gaps between matched characters', () => {
    const contiguous = fuzzyScore('abc', 'abcxxx')!;
    const gapped = fuzzyScore('abc', 'axbxcx')!;
    expect(contiguous).toBeGreaterThan(gapped);
  });

  it('penalizes longer targets at equal match quality', () => {
    const short = fuzzyScore('nav', 'nav')!;
    const long = fuzzyScore('nav', 'nav to somewhere else')!;
    expect(short).toBeGreaterThan(long);
  });

  it('scores the empty query for every target', () => {
    expect(fuzzyScore('', 'anything')).not.toBeNull();
  });
});

describe('commandScore', () => {
  it('takes the max of title and weighted keyword scores', () => {
    const viaTitle = commandScore('ide', { title: 'ide', keywords: ['zzz'] });
    const viaKeyword = commandScore('ide', { title: 'zzz', keywords: ['ide'] });
    expect(viaTitle).not.toBeNull();
    expect(viaKeyword).not.toBeNull();
    // Keyword hits are weighted ×0.9 → strictly below the same title hit.
    expect(viaKeyword!).toBeCloseTo(viaTitle! * 0.9, 5);
  });

  it('returns null when neither title nor keywords match', () => {
    expect(commandScore('zzz', { title: 'open ide', keywords: ['editor'] })).toBeNull();
  });
});
