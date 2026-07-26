import { type HTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

type Variant = 'neutral' | 'success' | 'warn' | 'danger' | 'info' | 'accent' | 'outline';
type Size = 'sm' | 'md';

const VARIANTS: Record<Variant, string> = {
  neutral: 'bg-surface-2 text-muted',
  success: 'bg-success-bg text-success',
  warn: 'bg-warn-bg text-warn',
  danger: 'bg-danger-bg text-danger',
  info: 'bg-info-bg text-info',
  accent: 'bg-accent text-accent-fg',
  outline: 'border border-border text-muted',
};

const SIZES: Record<Size, string> = {
  sm: 'px-1.5 py-0 text-[11px] leading-4',
  md: 'px-2 py-0.5 text-xs',
};

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant;
  size?: Size;
  /** Leading status dot in the variant's foreground color. */
  dot?: boolean;
}

export function Badge({ variant = 'neutral', size = 'md', dot = false, className, children, ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full font-medium',
        VARIANTS[variant],
        SIZES[size],
        className,
      )}
      {...props}
    >
      {dot && <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}
