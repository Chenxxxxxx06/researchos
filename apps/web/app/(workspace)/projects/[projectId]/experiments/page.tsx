'use client';

import { use } from 'react';

import { ExperimentsDashboard } from '@/features/experiments/ExperimentsDashboard';

export default function ExperimentsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  return <ExperimentsDashboard projectId={projectId} />;
}
