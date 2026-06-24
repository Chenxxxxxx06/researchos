'use client';

import { useSession } from '@/lib/auth/session-context';
import { useWorkspaceStore } from '@/lib/store/workspace';
import { Skeleton } from '@/components/ui/skeleton';
import { ProjectList } from '@/features/projects/ProjectList';

export default function ProjectsPage() {
  const { data: me } = useSession();
  const currentOrgId = useWorkspaceStore((s) => s.currentOrgId);

  // The layout guarantees a session; pick the selected or first organization.
  const orgId = currentOrgId ?? me?.organizations[0]?.id ?? null;

  if (!orgId) {
    return <Skeleton className="h-24 w-full" />;
  }

  return <ProjectList organizationId={orgId} />;
}
