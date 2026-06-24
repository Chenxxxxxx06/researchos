'use client';

import { use } from 'react';

import { ProjectOverview } from '@/features/projects/ProjectOverview';

export default function ProjectOverviewPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);
  return <ProjectOverview projectId={projectId} />;
}
