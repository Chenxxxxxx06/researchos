'use client';

import { use } from 'react';

import { ReferencesWorkspace } from '@/features/references/ReferencesWorkspace';

export default function ReferencesPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  return <ReferencesWorkspace projectId={projectId} />;
}
