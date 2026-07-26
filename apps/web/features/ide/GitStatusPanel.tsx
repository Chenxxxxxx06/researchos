'use client';

/**
 * Real porcelain status header (D5). Rewritten from the always-clean stub into a
 * `StatusHeader` used by GitTimelinePanel. The `GitStatusPanel` name is kept as
 * an alias so no external import breaks.
 */

import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, GitBranch } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { ApiError } from '@/lib/api/client';
import { getGitStatus, type GitStatus } from '@/lib/api/git';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';

export function StatusHeader({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const openTab = useIdeStore((s) => s.openTab);
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading, isError } = useQuery<GitStatus, ApiError>({
    queryKey: ['git-status', projectId],
    queryFn: () => getGitStatus(projectId),
  });

  return (
    <div className="border-b border-border px-3 py-2">
      <div className="flex items-center gap-2 text-xs">
        <GitBranch className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
        {isLoading && <span className="text-muted">{t('common.loading')}</span>}
        {isError && <span className="text-danger">{t('common.error')}</span>}
        {data && (
          <>
            <span className="truncate font-mono text-text" title={data.branch}>
              {data.branch}
            </span>
            {data.clean ? (
              <Badge variant="success" size="sm">
                {t('ide.clean')}
              </Badge>
            ) : (
              <button
                type="button"
                onClick={() => setExpanded((v) => !v)}
                className="inline-flex items-center gap-1 outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
              >
                <Badge variant="warn" size="sm">
                  {t('ide.changedCount', { n: data.files.length })}
                </Badge>
                {data.files.length > 0 &&
                  (expanded ? (
                    <ChevronDown className="h-3 w-3 text-muted" aria-hidden="true" />
                  ) : (
                    <ChevronRight className="h-3 w-3 text-muted" aria-hidden="true" />
                  ))}
              </button>
            )}
          </>
        )}
      </div>

      {data && !data.clean && expanded && data.files.length > 0 && (
        <ul className="mt-1.5 space-y-0.5">
          {data.files.map((f) => (
            <li key={f.path}>
              <button
                type="button"
                onClick={() => openTab(f.path)}
                className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-xs hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
              >
                <span className="w-4 shrink-0 text-center font-mono text-[10px] uppercase text-muted">
                  {f.state.charAt(0)}
                </span>
                <span className="truncate font-mono text-muted" title={f.path}>
                  {f.path}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Back-compat alias (the route no longer imports this directly). */
export const GitStatusPanel = StatusHeader;
