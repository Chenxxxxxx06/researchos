'use client';

import { useQuery } from '@tanstack/react-query';
import { ArrowUpRight, FolderKanban, Layers3 } from 'lucide-react';
import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import { listProjects, type Page, type Project } from '@/lib/api/projects';
import { useI18n } from '@/lib/i18n';

import { CreateProjectDialog } from './CreateProjectDialog';

export function ProjectList({ organizationId }: { organizationId: string }) {
  const { locale } = useI18n();
  const zh = locale === 'zh-CN';
  const projects = useQuery<Page<Project>, ApiError>({
    queryKey: ['projects', organizationId],
    queryFn: () => listProjects(organizationId),
  });
  const items = [...(projects.data?.items ?? [])].sort((a, b) => b.updated_at.localeCompare(a.updated_at));

  return (
    <div className="mx-auto max-w-[92rem]">
      <header className="mission-grid -mx-5 -mt-5 border-b border-border px-5 py-8 lg:-mx-6 lg:-mt-6 lg:px-8 xl:-mx-8 xl:-mt-8 xl:px-10 xl:py-10">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2 text-xs font-medium text-muted">
              <Layers3 className="h-4 w-4 text-accent" aria-hidden="true" />
              {zh ? '研究工作区' : 'Research workspaces'}
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em] text-text sm:text-4xl">
              {zh ? '从一个明确问题开始' : 'Start from one clear question'}
            </h1>
            <p className="mt-3 max-w-xl text-sm leading-6 text-muted">
              {zh ? '每个项目都连接文献证据、Agent 任务、代码版本、实验结果和论文主张。' : 'Each project connects literature evidence, agent work, code versions, experiments, and paper claims.'}
            </p>
          </div>
          <CreateProjectDialog organizationId={organizationId} />
        </div>
      </header>

      <section className="py-7 lg:py-8">
        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-base font-semibold tracking-[-0.02em] text-text">{zh ? '最近项目' : 'Recent projects'}</h2>
            <p className="mt-1 text-xs text-muted">
              {projects.data ? (zh ? `共 ${projects.data.total} 个项目` : `${projects.data.total} projects`) : (zh ? '正在同步项目' : 'Syncing projects')}
            </p>
          </div>
        </div>

        {projects.isLoading && (
          <div className="workspace-panel divide-y divide-border overflow-hidden">
            {[0, 1, 2].map((item) => <Skeleton key={item} className="h-24 w-full rounded-none" />)}
          </div>
        )}

        {projects.isError && (
          <div className="workspace-panel border-danger/25 bg-danger-bg p-5 text-sm text-danger">
            {projects.error.message}
          </div>
        )}

        {!projects.isLoading && !projects.isError && items.length === 0 && (
          <EmptyState
            icon={FolderKanban}
            title={zh ? '还没有研究项目' : 'No research projects yet'}
            body={zh ? '创建项目后，资料、任务、实验和论文会进入同一条可追溯工作流。' : 'Create a project to keep evidence, missions, experiments, and writing in one traceable workflow.'}
            actions={<CreateProjectDialog organizationId={organizationId} />}
          />
        )}

        {items.length > 0 && (
          <div className="workspace-panel divide-y divide-border overflow-hidden">
            {items.map((project, index) => (
              <Link
                key={project.id}
                href={`/projects/${project.id}/overview`}
                className="group grid min-h-24 items-center gap-4 px-4 py-4 hover:bg-surface-2/70 sm:grid-cols-[3rem_minmax(0,1fr)_auto_auto] sm:px-5"
              >
                <div className="grid h-11 w-11 place-items-center rounded-md border border-border bg-bg font-mono text-sm font-semibold text-accent shadow-elev1">
                  {String(index + 1).padStart(2, '0')}
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="truncate text-sm font-semibold tracking-[-0.01em] text-text">{project.name}</h3>
                    <Badge variant={project.status === 'active' ? 'success' : 'neutral'} size="sm">{project.status}</Badge>
                  </div>
                  <p className="mt-1 line-clamp-1 text-xs text-muted">
                    {project.description || project.field || (zh ? '尚未填写项目描述' : 'No project description yet')}
                  </p>
                </div>
                <div className="hidden text-right sm:block">
                  <p className="text-[10px] text-faint">{zh ? '最近更新' : 'Updated'}</p>
                  <p className="mt-1 font-mono text-[11px] text-muted">{new Date(project.updated_at).toLocaleDateString(locale)}</p>
                </div>
                <ArrowUpRight className="h-4 w-4 text-faint transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" aria-hidden="true" />
              </Link>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
