'use client';

import { useQuery } from '@tanstack/react-query';

import { getProject, type Project } from '@/lib/api/projects';
import { ApiError } from '@/lib/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

// Modules that light up in later phases. Rendered as empty placeholders now.
const FUTURE_MODULES = ['Running experiments', 'Paper drafts', 'Installed skills'];

export function ProjectOverview({ projectId }: { projectId: string }) {
  const { data: project, isLoading, isError, error } = useQuery<Project, ApiError>({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  if (isLoading) {
    return <Skeleton className="h-40 w-full" />;
  }

  if (isError) {
    return (
      <Card>
        <CardContent>
          <p className="text-sm text-red-600">
            {error?.status === 404
              ? 'Project not found or you do not have access.'
              : (error?.message ?? 'Failed to load project.')}
          </p>
        </CardContent>
      </Card>
    );
  }

  if (!project) return null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-lg font-semibold">{project.name}</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {project.field ?? 'No field set'} · {project.status}
        </p>
        {project.description && (
          <p className="mt-2 max-w-2xl text-sm text-neutral-700">{project.description}</p>
        )}
        <div className="mt-3 flex gap-2">
          <a
            href={`/projects/${project.id}/research`}
            className="inline-block rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
          >
            Open Research Copilot
          </a>
          <a
            href={`/projects/${project.id}/ide`}
            className="inline-block rounded-md border border-neutral-300 bg-white px-4 py-2 text-sm font-medium text-neutral-900 hover:bg-neutral-50"
          >
            Open AI IDE
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {FUTURE_MODULES.map((title) => (
          <Card key={title}>
            <CardHeader>
              <CardTitle>{title}</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-neutral-400">Coming soon</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
