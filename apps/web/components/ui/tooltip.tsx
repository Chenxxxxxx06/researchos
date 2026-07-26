'use client';

/**
 * Lightweight tooltip: shows on hover (350ms delay) and focus (immediate).
 * Absolute in-place positioning, pointer-events-none, aria-describedby wired.
 */

import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from 'react';

import { formatChord } from '@/lib/shortcuts/keys';
import { Kbd } from '@/components/ui/kbd';
import { cn } from '@/lib/utils';

const SIDES = {
  top: 'bottom-full left-1/2 mb-1.5 -translate-x-1/2',
  bottom: 'top-full left-1/2 mt-1.5 -translate-x-1/2',
  right: 'left-full top-1/2 ml-1.5 -translate-y-1/2',
} as const;

export interface TooltipProps {
  content: ReactNode;
  /** Chord spec (e.g. 'g i') rendered as a <Kbd> suffix. */
  shortcut?: string;
  side?: keyof typeof SIDES;
  children: ReactNode;
  className?: string;
}

export function Tooltip({ content, shortcut, side = 'top', children, className }: TooltipProps) {
  const [visible, setVisible] = useState(false);
  const timer = useRef<number | null>(null);
  const id = useId();

  const clear = useCallback(() => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
    }
  }, []);

  useEffect(() => clear, [clear]);

  const showDelayed = useCallback(() => {
    clear();
    timer.current = window.setTimeout(() => setVisible(true), 350);
  }, [clear]);

  const hide = useCallback(() => {
    clear();
    setVisible(false);
  }, [clear]);

  return (
    <span
      className={cn('relative inline-flex', className)}
      onMouseEnter={showDelayed}
      onMouseLeave={hide}
      onFocus={() => {
        clear();
        setVisible(true);
      }}
      onBlur={hide}
      aria-describedby={visible ? id : undefined}
    >
      {children}
      {visible && (
        <span
          role="tooltip"
          id={id}
          className={cn(
            'pointer-events-none absolute z-50 flex items-center gap-1.5 whitespace-nowrap',
            'rounded-md border border-border bg-overlay px-2 py-1 text-xs text-text shadow-elev2',
            SIDES[side],
          )}
        >
          {content}
          {shortcut && <Kbd keys={formatChord(shortcut)} raw />}
        </span>
      )}
    </span>
  );
}
