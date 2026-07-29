import { ResearchInboxWorkspace } from '@/features/inbox/ResearchInboxWorkspace';

export default async function InboxPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ResearchInboxWorkspace projectId={projectId} />;
}
