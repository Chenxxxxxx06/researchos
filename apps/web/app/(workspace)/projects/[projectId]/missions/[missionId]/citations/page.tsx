import { CitationAuditWorkspace } from '@/features/missions/CitationAuditWorkspace';

export default async function CitationAuditPage({ params }: { params: Promise<{ projectId: string; missionId: string }> }) {
  const { projectId, missionId } = await params;
  return <CitationAuditWorkspace projectId={projectId} missionId={missionId} />;
}
