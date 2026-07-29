import { ReviewerWorkspace } from '@/features/reviewer/ReviewerWorkspace';

export default async function ReviewerPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ReviewerWorkspace projectId={projectId} />;
}
