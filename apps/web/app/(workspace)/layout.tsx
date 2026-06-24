'use client';

import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { ApiError } from '@/lib/api/client';
import { useSession } from '@/lib/auth/session-context';
import { Skeleton } from '@/components/ui/skeleton';
import { SideRail } from '@/features/workspace/SideRail';
import { TopBar } from '@/features/workspace/TopBar';

export default function WorkspaceLayout({ children }: { children: ReactNode }) {
  const router = useRouter();
  const { data: me, isLoading, error } = useSession();

  // Backend is authoritative: if the session is invalid, leave the workspace.
  useEffect(() => {
    if (error instanceof ApiError && error.status === 401) {
      router.replace('/login');
    }
  }, [error, router]);

  if (isLoading) {
    return (
      <div className="min-h-screen p-6">
        <Skeleton className="mb-4 h-14 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!me) {
    return null; // Redirecting to /login.
  }

  return (
    <div className="flex min-h-screen flex-col">
      <TopBar me={me} />
      <div className="flex flex-1">
        <SideRail />
        <main className="flex-1 bg-neutral-50 p-6">{children}</main>
      </div>
    </div>
  );
}
