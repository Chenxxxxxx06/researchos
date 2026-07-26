import { formatChord } from '@/lib/shortcuts/keys';
import { cn } from '@/lib/utils';

export interface KbdProps {
  /** Chord spec ('mod+k', 'g i') formatted platform-aware, or raw text. */
  keys: string;
  /** Skip chord formatting and render `keys` verbatim. */
  raw?: boolean;
  className?: string;
}

/** Platform-aware keyboard hint: `mod+k` → ⌘K on macOS, Ctrl K elsewhere. */
export function Kbd({ keys, raw = false, className }: KbdProps) {
  return <kbd className={cn(className)}>{raw ? keys : formatChord(keys)}</kbd>;
}
