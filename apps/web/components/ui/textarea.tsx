import { forwardRef, type TextareaHTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      'min-h-20 w-full rounded-md border border-border-strong bg-surface px-3 py-2 text-sm text-text shadow-[inset_0_1px_0_rgb(var(--color-text)/0.025)]',
      'transition-[border-color,box-shadow,background-color] duration-150 placeholder:text-faint hover:border-accent/45 focus-visible:bg-overlay focus-visible:outline-none',
      'focus-visible:border-accent/70 focus-visible:ring-2 focus-visible:ring-focus/30 disabled:opacity-50',
      'aria-[invalid=true]:border-danger',
      className,
    )}
    {...props}
  />
));
Textarea.displayName = 'Textarea';
