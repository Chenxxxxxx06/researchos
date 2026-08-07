import { ManagementWorkspace } from '@/features/management/ManagementWorkspace';

export default async function ManagementPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  return <ManagementWorkspace projectId={projectId} />;
}
