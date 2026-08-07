import { ExperimentPlanWorkspace } from '@/features/missions/ExperimentPlanWorkspace';

export default async function ExperimentPlanPage({ params }: { params: Promise<{ projectId: string; missionId: string }> }) {
  const { projectId, missionId } = await params;
  return <ExperimentPlanWorkspace projectId={projectId} missionId={missionId} />;
}
