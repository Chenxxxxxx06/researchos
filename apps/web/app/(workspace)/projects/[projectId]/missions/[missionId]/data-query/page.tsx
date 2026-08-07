import { DataLabWorkspace } from '@/features/missions/DataLabWorkspace';

export default async function DataQueryPage({ params }: { params: Promise<{ projectId: string; missionId: string }> }) {
  const { projectId, missionId } = await params;
  return <DataLabWorkspace projectId={projectId} missionId={missionId} />;
}
