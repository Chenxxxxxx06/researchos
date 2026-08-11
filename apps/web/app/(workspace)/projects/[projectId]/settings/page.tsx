import { redirect } from 'next/navigation';

export default async function SettingsPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params;
  redirect(`/projects/${projectId}/manage?tab=settings`);
}
