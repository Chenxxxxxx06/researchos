'use client';

/**
 * Result-anchors panel (partition: frontend-paper, Design C.1).
 *
 * Browse project result anchors with live values + staleness, insert the macro
 * at the cursor, delete, refresh values, and update-all when stale. Project-scoped
 * routes (CONSOLIDATION §5); any 404 renders the "unavailable" state (retry:false).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import { listAnchors, refreshAnchors, deleteAnchor, type Anchor } from '@/lib/api/anchors';
import { useI18n } from '@/lib/i18n';
import { Anchor as AnchorIcon } from 'lucide-react';

function formatValue(a: Anchor): string {
  if (a.captured_value === null) return '—';
  return `${(a.captured_value * a.scale).toFixed(a.decimals)}${a.suffix}`;
}

export function AnchorsPanel({
  projectId,
  onInsert,
}: {
  projectId: string;
  onInsert: (macro: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const anchors = useQuery({
    queryKey: ['anchors', projectId],
    queryFn: () => listAnchors(projectId),
    retry: false,
  });

  const refresh = useMutation({
    mutationFn: () => refreshAnchors(projectId),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['anchors', projectId] });
      qc.invalidateQueries({ queryKey: ['anchor-staleness', projectId] });
      toast({ title: t('paper.anchors.refreshed', { n: res.refreshed }) });
    },
  });

  const remove = useMutation({
    mutationFn: (id: string) => deleteAnchor(projectId, id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['anchors', projectId] }),
  });

  if (anchors.isLoading) return <Skeleton className="h-40 w-full" />;
  if (anchors.isError)
    return <EmptyState icon={AnchorIcon} title={t('paper.anchors.unavailable')} />;

  const items = anchors.data ?? [];
  if (items.length === 0)
    return (
      <EmptyState
        icon={AnchorIcon}
        title={t('paper.anchors.empty')}
        body={t('paper.anchors.emptyBody')}
      />
    );

  const anyStale = items.some((a) => a.stale);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-end gap-2">
        {anyStale && (
          <Button size="sm" variant="secondary" onClick={() => refresh.mutate()} loading={refresh.isPending}>
            {t('paper.anchors.updateAll')}
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => refresh.mutate()} loading={refresh.isPending}>
          {t('paper.anchors.refresh')}
        </Button>
      </div>
      <ul className="space-y-1.5">
        {items.map((a) => (
          <li key={a.id} className="rounded-md border border-border bg-surface p-2.5">
            <div className="flex items-center justify-between gap-2">
              <code className="font-mono text-xs text-text">{a.macro}</code>
              <span className="font-mono text-sm font-semibold text-text">{formatValue(a)}</span>
            </div>
            <div className="mt-1.5 flex items-center gap-1.5">
              <Badge variant="neutral" size="sm">
                {a.run_id ? t('paper.anchors.pinned') : t('paper.anchors.latest')}
              </Badge>
              {a.stale && (
                <Badge variant="warn" size="sm" dot>
                  {t('paper.anchors.stale')}
                </Badge>
              )}
              <span className="ml-auto flex gap-1">
                <Button size="sm" variant="ghost" onClick={() => onInsert(a.macro)}>
                  {t('paper.anchors.insert')}
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    if (window.confirm(t('paper.anchors.deleteConfirm'))) remove.mutate(a.id);
                  }}
                >
                  {t('common.delete')}
                </Button>
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
