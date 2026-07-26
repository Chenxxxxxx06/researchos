import { type HTMLAttributes } from 'react';

import { cn } from '@/lib/utils';

export function Skeleton({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('animate-pulse rounded-md bg-surface-2', className)} {...props} />;
}

/** Convenience: n stacked text-line skeletons (last line shortened). */
function SkeletonText({ lines = 3, className }: { lines?: number; className?: string }) {
  return (
    <div className={cn('space-y-2', className)}>
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={cn('h-4', i === lines - 1 ? 'w-3/5' : 'w-full')} />
      ))}
    </div>
  );
}

Skeleton.Text = SkeletonText;
