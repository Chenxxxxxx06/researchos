import { forwardRef, type InputHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text shadow-[inset_0_1px_0_rgb(var(--color-text)/0.025)]',
        'transition-[border-color,box-shadow,background-color] duration-150 placeholder:text-faint hover:border-accent/45 focus-visible:bg-overlay focus-visible:outline-none',
        'focus-visible:border-accent/70 focus-visible:ring-2 focus-visible:ring-focus/30 disabled:opacity-50',
        'aria-[invalid=true]:border-danger',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
