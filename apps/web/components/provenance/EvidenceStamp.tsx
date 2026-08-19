import { cn } from '@/lib/utils';

type Tone = 'neutral' | 'success' | 'warn' | 'danger' | 'accent';

const TONES: Record<Tone, string> = {
  neutral: 'border-border text-muted',
  success: 'border-success/40 text-success',
  warn: 'border-warn/40 text-warn',
  danger: 'border-danger/40 text-danger',
  accent: 'border-accent/40 text-accent',
};

export interface EvidenceStampProps {
  status: string;
  tone?: Tone;
  id?: string;
  date?: string;
  className?: string;
}

/** Compact archival/evidence stamp used for statuses that carry audit weight. */
export function EvidenceStamp({ status, tone = 'neutral', id, date, className }: EvidenceStampProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded border bg-surface px-2 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.12em]',
        TONES[tone],
        className,
      )}
    >
      <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />
      {status}
      {id && <span className="text-faint">· {id}</span>}
      {date && <span className="hidden text-faint sm:inline">· {date}</span>}
    </span>
  );
}
