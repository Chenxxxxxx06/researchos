'use client';

import { use } from 'react';

import { ReviewWorkspace } from '@/features/missions/ReviewWorkspace';

export default function MissionReviewPage({ params }: { params: Promise<{ projectId: string; missionId: string }> }) {
  const { projectId, missionId } = use(params);
  return <ReviewWorkspace projectId={projectId} missionId={missionId} />;
}
