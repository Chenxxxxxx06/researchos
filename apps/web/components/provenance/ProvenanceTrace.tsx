import { ArrowRight } from 'lucide-react';

import { cn } from '@/lib/utils';

export interface ProvenanceNode {
  label: string;
  state?: 'done' | 'active' | 'todo';
}

const DEFAULT_NODES: ProvenanceNode[] = [
  { label: '来源', state: 'done' },
  { label: '任务', state: 'done' },
  { label: '实验', state: 'active' },
  { label: '论文', state: 'todo' },
];

export interface ProvenanceTraceProps {
  nodes?: ProvenanceNode[];
  className?: string;
}

/** Compact trace showing how a research output is linked back to sources. */
export function ProvenanceTrace({ nodes = DEFAULT_NODES, className }: ProvenanceTraceProps) {
  return (
    <div className={cn('flex flex-wrap items-center gap-1 font-mono text-[10px] uppercase tracking-[0.12em]', className)}>
      {nodes.map((node, index) => (
        <span key={`${node.label}-${index}`} className="flex items-center gap-1">
          {index > 0 && <ArrowRight className="h-3 w-3 text-faint" aria-hidden="true" />}
          <span
            className={cn(
              'rounded border px-1.5 py-0.5',
              node.state === 'done' && 'border-success/30 bg-success-bg/50 text-success',
              node.state === 'active' && 'border-accent/40 bg-accent/10 text-accent',
              node.state === 'todo' && 'border-border bg-surface-2 text-faint',
              !node.state && 'border-border bg-surface-2 text-muted',
            )}
          >
            {node.label}
          </span>
        </span>
      ))}
    </div>
  );
}
