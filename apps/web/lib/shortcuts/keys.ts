/**
 * Chord parsing/formatting for the shortcut layer and <Kbd>.
 *
 * Specs: chords `mod+k`, `mod+enter`, `shift+?`, single keys `?`; sequences
 * are space-separated (`g i`) and handled by the shortcut provider, not here.
 * `mod` resolves to ⌘ on macOS and Ctrl elsewhere.
 *
 * Pure module (no DOM types beyond KeyboardEvent) — unit-tested in node.
 */

export interface Chord {
  /** Normalized lowercase key ('k', 'enter', '?'). */
  key: string;
  ctrl: boolean;
  meta: boolean;
  alt: boolean;
  shift: boolean;
}

let cachedIsMac: boolean | null = null;

export function isMacPlatform(): boolean {
  if (cachedIsMac !== null) return cachedIsMac;
  if (typeof navigator === 'undefined') return false; // node/test environment
  cachedIsMac = /mac|iphone|ipad|ipod/i.test(navigator.platform ?? '');
  return cachedIsMac;
}

/** A sequence spec is space-separated keys, e.g. 'g i'. */
export function isSequence(spec: string): boolean {
  return spec.trim().includes(' ');
}

/**
 * Parse a chord spec ('mod+k') into modifier flags. `mac` overrides platform
 * detection (for tests); defaults to the runtime platform.
 */
export function parseChord(spec: string, mac: boolean = isMacPlatform()): Chord {
  const parts = spec.toLowerCase().split('+');
  const chord: Chord = { key: '', ctrl: false, meta: false, alt: false, shift: false };
  for (const part of parts) {
    if (part === 'mod') {
      if (mac) chord.meta = true;
      else chord.ctrl = true;
    } else if (part === 'ctrl' || part === 'control') chord.ctrl = true;
    else if (part === 'meta' || part === 'cmd') chord.meta = true;
    else if (part === 'alt' || part === 'option') chord.alt = true;
    else if (part === 'shift') chord.shift = true;
    else chord.key = part;
  }
  return chord;
}

const MAC_KEY_GLYPHS: Record<string, string> = {
  enter: '↵',
  escape: 'Esc',
  esc: 'Esc',
  backspace: '⌫',
  arrowup: '↑',
  arrowdown: '↓',
  arrowleft: '←',
  arrowright: '→',
};

const GENERIC_KEY_NAMES: Record<string, string> = {
  enter: 'Enter',
  escape: 'Esc',
  esc: 'Esc',
  backspace: 'Backspace',
  arrowup: '↑',
  arrowdown: '↓',
  arrowleft: '←',
  arrowright: '→',
};

function formatKey(key: string, mac: boolean): string {
  const named = mac ? MAC_KEY_GLYPHS[key] : GENERIC_KEY_NAMES[key];
  if (named) return named;
  return key.length === 1 ? key.toUpperCase() : key.charAt(0).toUpperCase() + key.slice(1);
}

/**
 * Human-readable chord: 'mod+k' → '⌘K' (mac) / 'Ctrl K' (elsewhere).
 * Sequences ('g i') render their keys separated by spaces.
 */
export function formatChord(spec: string, mac: boolean = isMacPlatform()): string {
  if (isSequence(spec)) {
    return spec
      .trim()
      .split(/\s+/)
      .map((key) => formatKey(key.toLowerCase(), mac))
      .join(' ');
  }
  const chord = parseChord(spec, mac);
  const parts: string[] = [];
  if (mac) {
    if (chord.ctrl) parts.push('⌃');
    if (chord.alt) parts.push('⌥');
    if (chord.shift) parts.push('⇧');
    if (chord.meta) parts.push('⌘');
    parts.push(formatKey(chord.key, mac));
    return parts.join('');
  }
  if (chord.ctrl) parts.push('Ctrl');
  if (chord.meta) parts.push('Meta');
  if (chord.alt) parts.push('Alt');
  if (chord.shift) parts.push('Shift');
  parts.push(formatKey(chord.key, mac));
  return parts.join(' ');
}

/**
 * Match a KeyboardEvent against a chord. Shift is ignored for shifted
 * punctuation specs like '?' where e.key already reflects the shifted glyph.
 */
export function matchesChord(
  e: Pick<KeyboardEvent, 'key' | 'ctrlKey' | 'metaKey' | 'altKey' | 'shiftKey'>,
  chord: Chord,
): boolean {
  if (e.key.toLowerCase() !== chord.key) return false;
  if (e.ctrlKey !== chord.ctrl || e.metaKey !== chord.meta || e.altKey !== chord.alt) {
    return false;
  }
  const shiftedPunctuation = chord.key.length === 1 && !/[a-z0-9]/.test(chord.key);
  if (!shiftedPunctuation && e.shiftKey !== chord.shift) return false;
  return true;
}

/** True when keystrokes belong to the target (inputs, selects, Monaco, …). */
export function isEditableTarget(target: EventTarget | null): boolean {
  if (!target || !(target instanceof Element)) return false;
  const tag = target.tagName;
  if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (target instanceof HTMLElement && target.isContentEditable) return true;
  return target.closest('.monaco-editor') !== null;
}
