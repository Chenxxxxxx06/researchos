import { describe, expect, it } from 'vitest';

import { formatChord, isSequence, matchesChord, parseChord } from './keys';

describe('parseChord', () => {
  it('resolves mod to meta on mac', () => {
    expect(parseChord('mod+k', true)).toEqual({
      key: 'k',
      ctrl: false,
      meta: true,
      alt: false,
      shift: false,
    });
  });

  it('resolves mod to ctrl elsewhere', () => {
    expect(parseChord('mod+k', false)).toEqual({
      key: 'k',
      ctrl: true,
      meta: false,
      alt: false,
      shift: false,
    });
  });

  it('parses explicit modifiers and named keys', () => {
    expect(parseChord('ctrl+shift+enter', false)).toEqual({
      key: 'enter',
      ctrl: true,
      meta: false,
      alt: false,
      shift: true,
    });
  });

  it('parses bare punctuation', () => {
    expect(parseChord('?', false).key).toBe('?');
  });
});

describe('formatChord', () => {
  it('formats mac chords with glyphs and no separator', () => {
    expect(formatChord('mod+k', true)).toBe('⌘K');
    expect(formatChord('mod+enter', true)).toBe('⌘↵');
  });

  it('formats non-mac chords with names and spaces', () => {
    expect(formatChord('mod+k', false)).toBe('Ctrl K');
    expect(formatChord('mod+enter', false)).toBe('Ctrl Enter');
  });

  it('formats sequences by uppercasing keys', () => {
    expect(formatChord('g i', false)).toBe('G I');
  });
});

describe('isSequence', () => {
  it('detects space-separated sequences', () => {
    expect(isSequence('g i')).toBe(true);
    expect(isSequence('mod+k')).toBe(false);
  });
});

describe('matchesChord', () => {
  const event = (overrides: Partial<KeyboardEvent>) => ({
    key: 'k',
    ctrlKey: false,
    metaKey: false,
    altKey: false,
    shiftKey: false,
    ...overrides,
  });

  it('matches key + modifiers exactly', () => {
    const chord = parseChord('mod+k', false);
    expect(matchesChord(event({ ctrlKey: true }), chord)).toBe(true);
    expect(matchesChord(event({}), chord)).toBe(false);
    expect(matchesChord(event({ metaKey: true }), chord)).toBe(false);
  });

  it('ignores shift for shifted punctuation like ?', () => {
    const chord = parseChord('?', false);
    expect(matchesChord(event({ key: '?', shiftKey: true }), chord)).toBe(true);
    expect(matchesChord(event({ key: '?', shiftKey: false }), chord)).toBe(true);
  });

  it('requires shift when the spec says so for letters', () => {
    const chord = parseChord('shift+a', false);
    expect(matchesChord(event({ key: 'a', shiftKey: true }), chord)).toBe(true);
    expect(matchesChord(event({ key: 'a' }), chord)).toBe(false);
  });
});
