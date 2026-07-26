'use client';

import { use } from 'react';

import { IdeWorkspace } from '@/features/ide/IdeWorkspace';

export default function IdePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  return <IdeWorkspace projectId={projectId} />;
}
