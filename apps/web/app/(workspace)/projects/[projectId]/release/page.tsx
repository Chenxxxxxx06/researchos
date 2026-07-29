import { ResearchReleaseWorkspace } from '@/features/release/ResearchReleaseWorkspace';

export default async function ResearchReleasePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <ResearchReleaseWorkspace projectId={projectId} />;
}
