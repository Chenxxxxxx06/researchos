import type { LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';

import { cn } from '@/lib/utils';

export interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  body?: ReactNode;
  /** Action buttons (callers supply <Button> elements). */
  actions?: ReactNode;
  className?: string;
}

/** Shared empty/zero-data container; feature specs supply their own CTAs. */
export function EmptyState({ icon: Icon, title, body, actions, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border',
        'px-6 py-10 text-center',
        className,
      )}
    >
      {Icon && <Icon className="mb-1 h-8 w-8 text-faint" aria-hidden="true" />}
      <p className="text-sm font-medium text-text">{title}</p>
      {body && <div className="max-w-sm text-sm text-muted">{body}</div>}
      {actions && <div className="mt-3 flex items-center gap-2">{actions}</div>}
    </div>
  );
}
