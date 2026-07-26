'use client';

import { use } from 'react';

import { ReadingRoom } from '@/features/research/reading/ReadingRoom';

export default function ReadingRoomPage({
  params,
}: {
  params: Promise<{ projectId: string; paperId: string }>;
}) {
  const { projectId, paperId } = use(params);
  return <ReadingRoom projectId={projectId} paperId={paperId} />;
}
