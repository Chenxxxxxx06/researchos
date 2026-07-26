'use client';

import { use } from 'react';

import { ResearchWorkspace } from '@/features/research/ResearchWorkspace';

export default function ResearchPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  return <ResearchWorkspace projectId={projectId} />;
}
