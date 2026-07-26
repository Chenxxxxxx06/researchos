import { forwardRef, type InputHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        'h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text',
        'placeholder:text-faint focus-visible:outline-none',
        'focus-visible:ring-2 focus-visible:ring-focus/60 disabled:opacity-50',
        'aria-[invalid=true]:border-danger',
        className,
      )}
      {...props}
    />
  ),
);
Input.displayName = 'Input';
