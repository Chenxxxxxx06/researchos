'use client';

/**
 * Figures panel (partition: frontend-paper, Design D.1).
 *
 * Figure cards with thumbnails (blob-fetched assets), a style-preset select +
 * Regenerate (PATCH spec.style_slug then render — style lives inside the spec),
 * and Insert (writes an \includegraphics block into the buffer + PATCH
 * {latex_project_id, usage_path} per CONSOLIDATION §5). Project-scoped routes;
 * any 404 renders the "unavailable" state (retry:false).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { ImageIcon } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import {
  fetchFigureAssetUrl,
  listFigures,
  listStylePresets,
  renderFigure,
  updateFigure,
  type Figure,
} from '@/lib/api/figures';
import { useI18n } from '@/lib/i18n';

function slugify(name: string): string {
  return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') || 'figure';
}

function figureBlock(fig: Figure): string {
  const slug = slugify(fig.name);
  return [
    `% researchos:figure ${fig.id}`,
    '\\begin{figure}[t]',
    '  \\centering',
    `  \\includegraphics[width=\\linewidth]{figures/${slug}.png}`,
    `  \\caption{TODO: caption for ${fig.name}}`,
    `  \\label{fig:${slug}}`,
    '\\end{figure}',
    '',
  ].join('\n');
}

/** Blob-backed thumbnail; falls back to a placeholder box on any error. */
function FigureThumb({ projectId, figure }: { projectId: string; figure: Figure }) {
  const { t } = useI18n();
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let revoked: string | null = null;
    let active = true;
    setFailed(false);
    setUrl(null);
    if (figure.status !== 'rendered') return;
    fetchFigureAssetUrl(projectId, figure.id, 'png')
      .then((u) => {
        if (!active) {
          URL.revokeObjectURL(u);
          return;
        }
        revoked = u;
        setUrl(u);
      })
      .catch(() => active && setFailed(true));
    return () => {
      active = false;
      if (revoked) URL.revokeObjectURL(revoked);
    };
  }, [projectId, figure.id, figure.status, figure.last_rendered_at]);

  if (url && !failed) {
    // eslint-disable-next-line @next/next/no-img-element
    return <img src={url} alt={figure.name} className="h-28 w-full rounded object-contain" />;
  }
  return (
    <div className="flex h-28 w-full items-center justify-center rounded bg-surface-2 text-xs text-faint">
      {figure.status === 'rendering' || figure.status === 'pending'
        ? t('paper.figures.rendering')
        : t('paper.figures.noPreview')}
    </div>
  );
}

export function FiguresPanel({
  projectId,
  latexProjectId,
  onInsert,
}: {
  projectId: string;
  latexProjectId: string;
  onInsert: (block: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();

  const figures = useQuery({
    queryKey: ['figures', projectId],
    queryFn: () => listFigures(projectId),
    retry: false,
    refetchInterval: (query) => {
      const data = query.state.data as Figure[] | undefined;
      return data?.some((f) => f.status === 'pending' || f.status === 'rendering') ? 2500 : false;
    },
  });

  const presets = useQuery({
    queryKey: ['style-presets', projectId],
    queryFn: () => listStylePresets(projectId),
    retry: false,
  });

  const regenerate = useMutation({
    mutationFn: async ({ figure, styleSlug }: { figure: Figure; styleSlug: string }) => {
      await updateFigure(projectId, figure.id, {
        spec: { ...figure.spec, style_slug: styleSlug },
      });
      return renderFigure(projectId, figure.id, 'async');
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['figures', projectId] }),
  });

  const insert = useMutation({
    mutationFn: (figure: Figure) =>
      updateFigure(projectId, figure.id, {
        latex_project_id: latexProjectId,
        usage_path: 'main.tex',
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['figures', projectId] }),
  });

  if (figures.isLoading) return <Skeleton className="h-40 w-full" />;
  if (figures.isError)
    return <EmptyState icon={ImageIcon} title={t('paper.figures.unavailable')} />;

  const items = figures.data ?? [];
  if (items.length === 0)
    return (
      <EmptyState
        icon={ImageIcon}
        title={t('paper.figures.empty')}
        body={t('paper.figures.emptyBody')}
      />
    );

  return (
    <ul className="space-y-3">
      {items.map((fig) => (
        <li key={fig.id} className="rounded-lg border border-border bg-surface p-2.5">
          <FigureThumb projectId={projectId} figure={fig} />
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="truncate text-sm font-medium text-text">{fig.name}</span>
            <div className="flex shrink-0 gap-1">
              {fig.stale && (
                <Badge variant="warn" size="sm" dot>
                  {t('paper.figures.stale')}
                </Badge>
              )}
              {fig.style_outdated && (
                <Badge variant="warn" size="sm">
                  {t('paper.figures.styleOutdated')}
                </Badge>
              )}
              {fig.status === 'failed' && (
                <Badge variant="danger" size="sm">
                  {t('paper.figures.failed')}
                </Badge>
              )}
            </div>
          </div>
          <div className="mt-2 flex items-center gap-1.5">
            <select
              aria-label={t('paper.figures.style')}
              value={fig.rendered_style_slug ?? fig.spec.style_slug ?? ''}
              onChange={(e) => regenerate.mutate({ figure: fig, styleSlug: e.target.value })}
              disabled={regenerate.isPending || (presets.data?.length ?? 0) === 0}
              className="h-8 flex-1 rounded-md border border-border-strong bg-surface px-2 text-xs text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
            >
              {(presets.data ?? []).map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.name}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => regenerate.mutate({ figure: fig, styleSlug: fig.rendered_style_slug ?? fig.spec.style_slug ?? '' })}
              loading={regenerate.isPending}
            >
              {t('paper.figures.regenerate')}
            </Button>
            <Button
              size="sm"
              onClick={() => {
                onInsert(figureBlock(fig));
                insert.mutate(fig);
                toast({ title: t('paper.figures.inserted') });
              }}
            >
              {t('paper.figures.insert')}
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
