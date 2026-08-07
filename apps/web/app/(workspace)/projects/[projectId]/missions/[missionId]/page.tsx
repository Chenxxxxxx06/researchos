'use client';

import { use } from 'react';

import { MissionWorkspace } from '@/features/missions/MissionWorkspace';

export default function MissionPage({
  params,
}: {
  params: Promise<{ projectId: string; missionId: string }>;
}) {
  const { projectId, missionId } = use(params);
  return <MissionWorkspace projectId={projectId} missionId={missionId} />;
}
