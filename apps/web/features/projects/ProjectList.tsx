'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

import { listProjects, type Page, type Project } from '@/lib/api/projects';
import { ApiError } from '@/lib/api/client';
import { Card, CardContent, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

import { CreateProjectDialog } from './CreateProjectDialog';

export function ProjectList({ organizationId }: { organizationId: string }) {
  const { data, isLoading, isError, error } = useQuery<Page<Project>, ApiError>({
    queryKey: ['projects', organizationId],
    queryFn: () => listProjects(organizationId),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold">Projects</h1>
        <CreateProjectDialog organizationId={organizationId} />
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      )}

      {isError && (
        <Card>
          <CardContent>
            <p className="text-sm text-red-600">
              {error?.message ?? 'Failed to load projects.'}
            </p>
          </CardContent>
        </Card>
      )}

      {data && data.items.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="text-sm text-neutral-500">No projects yet.</p>
            <CreateProjectDialog organizationId={organizationId} />
          </CardContent>
        </Card>
      )}

      {data && data.items.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((project) => (
            <Link key={project.id} href={`/projects/${project.id}/overview`}>
              <Card className="transition-colors hover:border-neutral-300">
                <CardContent>
                  <CardTitle>{project.name}</CardTitle>
                  <p className="mt-1 text-xs text-neutral-500">
                    {project.field ?? 'No field set'}
                  </p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
