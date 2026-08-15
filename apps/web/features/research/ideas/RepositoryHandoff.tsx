'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Code2, Download, ExternalLink, GitFork, ShieldCheck } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  importRepositorySnapshot,
  listRepositorySnapshots,
  startRepositoryCoding,
} from '@/lib/api/git';
import { useI18n } from '@/lib/i18n';

export function RepositoryHandoff({ projectId, ideaId }: { projectId: string; ideaId: string }) {
  const { locale, t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const [url, setUrl] = useState('');
  const [approved, setApproved] = useState(false);

  const snapshots = useQuery({
    queryKey: ['repository-snapshots', projectId, ideaId],
    queryFn: () => listRepositorySnapshots(projectId, ideaId),
  });
  const latest = snapshots.data?.[0];
  const ready = snapshots.data?.find((item) => item.status === 'ready');

  const importRepository = useMutation({
    mutationFn: () =>
      importRepositorySnapshot(projectId, {
        idea_id: ideaId,
        github_url: url.trim(),
        approved: true,
      }),
    onSuccess: () => {
      setUrl('');
      setApproved(false);
      void queryClient.invalidateQueries({
        queryKey: ['repository-snapshots', projectId, ideaId],
      });
      void queryClient.invalidateQueries({ queryKey: ['git-log', projectId] });
      void queryClient.invalidateQueries({ queryKey: ['git-status', projectId] });
    },
  });

  const startCoding = useMutation({
    mutationFn: (snapshotId: string) => startRepositoryCoding(projectId, snapshotId),
    onSuccess: (result) => {
      router.push(
        `/projects/${projectId}/ide?session=${encodeURIComponent(result.coding_session_id)}`,
      );
    },
  });

  return (
    <section className="border-t border-border pt-3">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide text-faint">
          <GitFork className="h-3.5 w-3.5" aria-hidden="true" />
          {t('research.repository.title')}
        </p>
        {ready && <Badge variant="success" size="sm">{t('research.repository.ready')}</Badge>}
      </div>

      {ready ? (
        <div className="mt-2 space-y-2">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
            <Link
              href={ready.source_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1 font-medium text-text hover:text-accent"
            >
              {ready.source_owner}/{ready.source_repo}
              <ExternalLink className="h-3 w-3" aria-hidden="true" />
            </Link>
            <span className="font-mono">{ready.commit_sha?.slice(0, 12)}</span>
            <span>{ready.license_spdx ?? t('research.repository.licenseUnknown')}</span>
            <span>
              {t('research.repository.files', {
                n: ready.file_count,
                size: new Intl.NumberFormat(locale, {
                  style: 'unit',
                  unit: 'megabyte',
                  maximumFractionDigits: 1,
                }).format(ready.total_bytes / 1_000_000),
              })}
            </span>
          </div>
          <p className="truncate font-mono text-[10px] text-faint">{ready.destination_path}</p>
          <div className="flex flex-wrap gap-1.5">
            {ready.coding_session_id ? (
              <Button
                size="sm"
                className="h-7 text-[11px]"
                onClick={() =>
                  router.push(`/projects/${projectId}/ide?session=${ready.coding_session_id}`)
                }
              >
                <Code2 className="h-3 w-3" aria-hidden="true" />
                {t('research.repository.openIde')}
              </Button>
            ) : (
              <Button
                size="sm"
                className="h-7 text-[11px]"
                loading={startCoding.isPending}
                onClick={() => startCoding.mutate(ready.id)}
              >
                <Code2 className="h-3 w-3" aria-hidden="true" />
                {t('research.repository.startCoding')}
              </Button>
            )}
          </div>
          {startCoding.error instanceof Error && (
            <p className="text-[11px] text-danger">{startCoding.error.message}</p>
          )}
        </div>
      ) : (
        <div className="mt-2 space-y-2">
          <Input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://github.com/owner/repository"
            aria-label={t('research.repository.url')}
            className="h-8 font-mono text-[11px]"
          />
          <label className="flex items-start gap-2 text-[10px] leading-4 text-muted">
            <input
              type="checkbox"
              checked={approved}
              onChange={(event) => setApproved(event.target.checked)}
              className="mt-0.5 h-3.5 w-3.5 accent-[var(--color-accent)]"
            />
            <ShieldCheck className="mt-0.5 h-3 w-3 shrink-0 text-success" aria-hidden="true" />
            <span>{t('research.repository.approval')}</span>
          </label>
          <Button
            size="sm"
            variant="secondary"
            className="h-7 text-[11px]"
            loading={importRepository.isPending}
            disabled={!approved || !url.trim()}
            onClick={() => importRepository.mutate()}
          >
            <Download className="h-3 w-3" aria-hidden="true" />
            {t('research.repository.import')}
          </Button>
          {latest?.status === 'failed' && latest.error && (
            <p className="text-[11px] text-danger">{latest.error}</p>
          )}
          {importRepository.error instanceof Error && (
            <p className="text-[11px] text-danger">{importRepository.error.message}</p>
          )}
        </div>
      )}
    </section>
  );
}
