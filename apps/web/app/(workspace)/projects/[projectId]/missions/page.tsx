'use client';

import { use } from 'react';

import { MissionListWorkspace } from '@/features/missions/MissionListWorkspace';

export default function MissionsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  return <MissionListWorkspace projectId={projectId} />;
}
