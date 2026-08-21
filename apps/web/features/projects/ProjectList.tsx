'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

import { listProjects, type Page, type Project } from '@/lib/api/projects';
import { ApiError } from '@/lib/api/client';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

import { CreateProjectDialog } from './CreateProjectDialog';

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
}

export function ProjectList({ organizationId }: { organizationId: string }) {
  const { data, isLoading, isError, error } = useQuery<Page<Project>, ApiError>({
    queryKey: ['projects', organizationId],
    queryFn: () => listProjects(organizationId),
  });

  return (
    <div>
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-text">Projects</h1>
          <p className="mt-0.5 text-xs text-muted">Research workspaces with traceable evidence.</p>
        </div>
        <CreateProjectDialog organizationId={organizationId} />
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
          <Skeleton className="h-28" />
        </div>
      )}

      {isError && (
        <Card>
          <CardContent>
            <p className="text-sm text-danger">
              {error?.message ?? 'Failed to load projects.'}
            </p>
          </CardContent>
        </Card>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="text-sm text-muted">No projects yet.</p>
            <CreateProjectDialog organizationId={organizationId} />
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}/overview`}>
              <Card className="h-full transition-colors hover:border-border-strong">
                <CardContent className="flex h-full flex-col">
                  <div className="flex items-start justify-between gap-2">
                    <CardTitle className="truncate">{project.name}</CardTitle>
                    <Badge variant={project.status === 'active' ? 'success' : 'neutral'} size="sm" dot>
                      {project.status}
                    </Badge>
                  </div>
                  <p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">
                    {project.field ?? 'No field set'}
                  </p>
                  <div className="mt-auto flex items-center justify-between pt-4 text-[10px] uppercase tracking-wider text-faint">
                    <span className="font-mono">{formatDate(project.updated_at)}</span>
                    <span className="font-mono">{project.id.slice(0, 8)}</span>
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
