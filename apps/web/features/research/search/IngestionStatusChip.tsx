'use client';

import { AlertTriangle, Check, FileText } from 'lucide-react';

import type { IngestStatus } from '@/lib/api/papers';
import { useI18n, type DictKey } from '@/lib/i18n';
import { Tooltip } from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

type Tone = 'warn' | 'success' | 'muted' | 'danger';

const TONE_PILL: Record<Tone, string> = {
  warn: 'bg-warn-bg text-warn',
  success: 'bg-success-bg text-success',
  muted: 'bg-surface-2 text-muted',
  danger: 'bg-danger-bg text-danger',
};

const TONE_DOT: Record<Tone, string> = {
  warn: 'bg-warn',
  success: 'bg-success',
  muted: 'bg-faint',
  danger: 'bg-danger',
};

function meta(status: IngestStatus): { key: DictKey; tone: Tone; pulse: boolean } {
  switch (status) {
    case 'pending':
      return { key: 'research.ingest.pending', tone: 'warn', pulse: true };
    case 'running':
      return { key: 'research.ingest.running', tone: 'warn', pulse: true };
    case 'succeeded':
      return { key: 'research.ingest.fullText', tone: 'success', pulse: false };
    case 'abstract_only':
      return { key: 'research.ingest.abstractOnly', tone: 'muted', pulse: false };
    case 'failed':
      return { key: 'research.ingest.failed', tone: 'danger', pulse: false };
  }
}

export function IngestionStatusChip({
  status,
  variant = 'full',
}: {
  status: IngestStatus;
  variant?: 'full' | 'dot';
}) {
  const { t } = useI18n();
  const { key, tone, pulse } = meta(status);
  const label = t(key);

  if (variant === 'dot') {
    return (
      <Tooltip content={label}>
        <span
          aria-label={label}
          className={cn('inline-block h-2 w-2 rounded-full', TONE_DOT[tone], pulse && 'animate-pulse')}
        />
      </Tooltip>
    );
  }

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-medium leading-4',
        TONE_PILL[tone],
      )}
    >
      {pulse && <span aria-hidden="true" className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />}
      {status === 'succeeded' && <Check className="h-3 w-3" aria-hidden="true" />}
      {status === 'abstract_only' && <FileText className="h-3 w-3" aria-hidden="true" />}
      {status === 'failed' && <AlertTriangle className="h-3 w-3" aria-hidden="true" />}
      {label}
    </span>
  );
}
