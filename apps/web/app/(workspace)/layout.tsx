'use client';

import { useRouter } from 'next/navigation';
import { useEffect, type ReactNode } from 'react';

import { ApiError } from '@/lib/api/client';
import { useSession } from '@/lib/auth/session-context';
import { useBuiltinCommands } from '@/lib/command/builtin';
import { ShortcutProvider } from '@/lib/shortcuts';
import { CommandPalette } from '@/components/command/CommandPalette';
import { ShortcutCheatsheet } from '@/components/command/ShortcutCheatsheet';
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
    <ShortcutProvider>
      <WorkspaceCommands />
      <a href="#workspace-content" className="sr-only z-50 rounded-md bg-accent px-4 py-2 text-accent-fg focus:not-sr-only focus:fixed focus:left-4 focus:top-4">
        Skip to workspace content
      </a>
      <div className="flex min-h-[100dvh] flex-col bg-bg">
        <TopBar me={me} />
        <div className="flex flex-1 items-start">
          <SideRail />
          <main id="workspace-content" className="min-w-0 flex-1 bg-bg p-5 pb-24 lg:p-6 lg:pb-6 xl:p-8">{children}</main>
        </div>
      </div>
      <CommandPalette />
      <ShortcutCheatsheet />
    </ShortcutProvider>
  );
}

/** Hook host: registers built-in palette commands for the workspace. */
function WorkspaceCommands() {
  useBuiltinCommands();
  return null;
}
