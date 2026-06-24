'use client';

import { useI18n } from '@/lib/i18n';
import type { CompileJob } from '@/lib/api/paper';

interface PreviewPanelProps {
  job?: CompileJob | null;
  isCompiling?: boolean;
}

export function PreviewPanel({ job, isCompiling }: PreviewPanelProps) {
  const { t } = useI18n();

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-neutral-200 p-3">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          {t('paper.preview')}
        </h3>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {isCompiling && <p className="text-xs text-neutral-400">{t('paper.compiling')}</p>}

        {!isCompiling && job?.status === 'failed' && (
          <p className="whitespace-pre-wrap text-xs text-red-600">
            {job.error_summary ?? t('common.error')}
          </p>
        )}

        {!isCompiling && job?.preview && (
          <pre className="whitespace-pre-wrap text-xs leading-relaxed text-neutral-800">
            {job.preview}
          </pre>
        )}

        {!isCompiling && !job?.preview && job?.status !== 'failed' && (
          <p className="text-xs text-neutral-400">{t('paper.compile')}</p>
        )}
      </div>
    </div>
  );
}
