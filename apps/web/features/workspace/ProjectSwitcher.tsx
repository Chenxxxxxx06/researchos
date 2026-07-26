'use client';

import { useQuery } from '@tanstack/react-query';
import { useParams, usePathname, useRouter } from 'next/navigation';
import { ChevronsUpDown, FolderKanban } from 'lucide-react';

import { listProjects, type Page, type Project } from '@/lib/api/projects';
import { useI18n } from '@/lib/i18n';
import { useWorkspaceStore } from '@/lib/store/workspace';
import {
  Dropdown,
  DropdownItem,
  DropdownLabel,
  DropdownRadioItem,
  DropdownSeparator,
} from '@/components/ui/dropdown';

/**
 * Switch between projects while staying on the same sub-page (falls back to
 * /overview when the target has no matching sub-route context). Hidden when
 * the current route carries no projectId.
 */
export function ProjectSwitcher() {
  const { t } = useI18n();
  const router = useRouter();
  const pathname = usePathname();
  const params = useParams<{ projectId?: string }>();
  const currentOrgId = useWorkspaceStore((s) => s.currentOrgId);
  const projectId = params?.projectId ?? null;

  // Read-only use of the projects API (same key as ProjectList so the cache
  // is shared); only fetched while a project route is active.
  const projects = useQuery<Page<Project>>({
    queryKey: ['projects', currentOrgId],
    queryFn: () => listProjects(currentOrgId as string),
    enabled: Boolean(projectId && currentOrgId),
  });

  if (!projectId) return null;

  const items = projects.data?.items ?? [];
  const current = items.find((p) => p.id === projectId);

  const hrefFor = (targetId: string): string => {
    const swapped = pathname?.replace(/^\/projects\/[^/]+/, `/projects/${targetId}`);
    return swapped && swapped !== pathname ? swapped : `/projects/${targetId}/overview`;
  };

  return (
    <Dropdown
      panelClassName="min-w-56 max-h-80 overflow-y-auto"
      trigger={
        <button
          type="button"
          aria-label={t('nav.switchProject')}
          className="flex h-8 max-w-48 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 text-sm text-text hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
        >
          <FolderKanban className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
          <span className="truncate">{current?.name ?? t('nav.currentProject')}</span>
          <ChevronsUpDown className="h-3.5 w-3.5 shrink-0 text-faint" aria-hidden="true" />
        </button>
      }
    >
      <DropdownLabel>{t('nav.switchProject')}</DropdownLabel>
      {items.map((project) => (
        <DropdownRadioItem
          key={project.id}
          checked={project.id === projectId}
          onSelect={() => router.push(hrefFor(project.id))}
        >
          {project.name}
        </DropdownRadioItem>
      ))}
      <DropdownSeparator />
      <DropdownItem icon={FolderKanban} onSelect={() => router.push('/projects')}>
        {t('nav.allProjects')}
      </DropdownItem>
    </Dropdown>
  );
}
