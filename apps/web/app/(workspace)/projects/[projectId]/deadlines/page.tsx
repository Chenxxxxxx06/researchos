import { VenueDeadlinesWorkspace } from '@/features/venues/VenueDeadlinesWorkspace';

export default async function VenueDeadlinesPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  return <VenueDeadlinesWorkspace projectId={projectId} />;
}
