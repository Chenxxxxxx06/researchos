'use client';

import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';

import { getProject, type Project } from '@/lib/api/projects';
import { ApiError } from '@/lib/api/client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';

const MODULES = [
  { title: 'Running experiments', desc: 'Track ML experiments, metrics, and artifacts' },
  { title: 'Paper drafts', desc: 'Write LaTeX papers with AI assistance' },
  { title: 'Installed skills', desc: 'Extend with research skills' },
];

export function ProjectOverview({ projectId }: { projectId: string }) {
  const { data: project, isLoading, isError, error } = useQuery<Project, ApiError>({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  if (isLoading) return <Skeleton className="h-40 w-full" />;
  if (isError) return (
    <Card><CardContent className="p-6">
      <p className="text-sm text-red-600">{error?.status === 404 ? 'Project not found.' : error?.message}</p>
    </CardContent></Card>
  );
  if (!project) return null;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-neutral-900">{project.name}</h1>
        <p className="mt-1 text-sm text-neutral-500">
          {project.field ?? 'General'} · {project.status}
        </p>
        {project.description && <p className="mt-3 max-w-2xl text-sm leading-relaxed text-neutral-600">{project.description}</p>}
      </div>

      {/* Core modules */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Link href={`/projects/${project.id}/research`} className="group rounded-xl border border-neutral-200 bg-white p-6 shadow-sm transition-all hover:border-neutral-400 hover:shadow-md">
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-600 text-lg">🔍</div>
          <h3 className="font-semibold text-neutral-900 group-hover:text-neutral-700">Research Copilot</h3>
          <p className="mt-1 text-sm text-neutral-500">Search papers, generate ideas, and get critic reviews.</p>
        </Link>
        <Link href={`/projects/${project.id}/ide`} className="group rounded-xl border border-neutral-200 bg-white p-6 shadow-sm transition-all hover:border-neutral-400 hover:shadow-md">
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600 text-lg">⌨️</div>
          <h3 className="font-semibold text-neutral-900 group-hover:text-neutral-700">AI IDE</h3>
          <p className="mt-1 text-sm text-neutral-500">Edit code with AI, review patches, and manage files.</p>
        </Link>
        <Link href={`/projects/${project.id}/experiments`} className="group rounded-xl border border-neutral-200 bg-white p-6 shadow-sm transition-all hover:border-neutral-400 hover:shadow-md">
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-600 text-lg">📊</div>
          <h3 className="font-semibold text-neutral-900 group-hover:text-neutral-700">Experiments</h3>
          <p className="mt-1 text-sm text-neutral-500">View runs, metrics, logs, and AI analysis.</p>
        </Link>
        <Link href={`/projects/${project.id}/paper`} className="group rounded-xl border border-neutral-200 bg-white p-6 shadow-sm transition-all hover:border-neutral-400 hover:shadow-md">
          <div className="mb-2 flex h-10 w-10 items-center justify-center rounded-lg bg-purple-50 text-purple-600 text-lg">📝</div>
          <h3 className="font-semibold text-neutral-900 group-hover:text-neutral-700">Paper Workspace</h3>
          <p className="mt-1 text-sm text-neutral-500">Write LaTeX with AI assistant and live preview.</p>
        </Link>
      </div>

      {/* Coming soon */}
      <div>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-neutral-400">Coming soon</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {MODULES.map((m) => (
            <Card key={m.title}>
              <CardHeader><CardTitle className="text-sm text-neutral-500">{m.title}</CardTitle></CardHeader>
              <CardContent><p className="text-xs text-neutral-400">{m.desc}</p></CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
