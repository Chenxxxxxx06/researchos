'use client';

import { use } from 'react';

import { PaperWorkspace } from '@/features/paper/PaperWorkspace';

export default function PaperPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  return <PaperWorkspace projectId={projectId} />;
}
