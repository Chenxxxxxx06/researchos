'use client';

import { use } from 'react';
import { useSearchParams } from 'next/navigation';

import { IdeWorkspace } from '@/features/ide/IdeWorkspace';

export default function IdePage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  const searchParams = useSearchParams();
  return <IdeWorkspace projectId={projectId} initialSessionId={searchParams.get('session')} />;
}
