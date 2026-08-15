import { AgentOrchestrationWorkspace } from '@/features/orchestration/AgentOrchestrationWorkspace';

export default async function OrchestrationPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <AgentOrchestrationWorkspace projectId={projectId} />;
}
