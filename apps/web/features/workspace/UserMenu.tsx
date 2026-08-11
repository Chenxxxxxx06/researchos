'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { FolderCog, LogOut } from 'lucide-react';

import { logout, type MeResponse } from '@/lib/api/auth';
import { useI18n } from '@/lib/i18n';
import {
  Dropdown,
  DropdownItem,
  DropdownLabel,
  DropdownSeparator,
} from '@/components/ui/dropdown';

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  if (parts.length === 1) return parts[0]!.slice(0, 2).toUpperCase();
  return (parts[0]![0]! + parts[parts.length - 1]![0]!).toUpperCase();
}

export function UserMenu({ me }: { me: MeResponse }) {
  const { t } = useI18n();
  const router = useRouter();
  const queryClient = useQueryClient();
  const params = useParams<{ projectId?: string }>();
  const projectId = params?.projectId;

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear();
      router.push('/login');
      router.refresh();
    },
  });

  return (
    <Dropdown
      align="end"
      panelClassName="min-w-52"
      trigger={
        <button
          type="button"
          aria-label={t('common.openMenu')}
          className="flex h-8 w-8 items-center justify-center rounded-full bg-accent text-xs font-semibold text-accent-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
        >
          {initials(me.user.display_name)}
        </button>
      }
    >
      <DropdownLabel>
        <span className="block text-[11px] uppercase tracking-wide">{t('common.signedInAs')}</span>
        <span className="mt-0.5 block truncate text-sm font-medium text-text">
          {me.user.display_name}
        </span>
        <span className="block truncate text-xs text-faint">{me.user.email}</span>
      </DropdownLabel>
      <DropdownSeparator />
      {projectId && (
        <DropdownItem
          icon={FolderCog}
          shortcut="g n"
          onSelect={() => router.push(`/projects/${projectId}/manage?tab=settings`)}
        >
          {t('nav.manage')}
        </DropdownItem>
      )}
      {projectId && <DropdownSeparator />}
      <DropdownItem
        icon={LogOut}
        destructive
        disabled={logoutMutation.isPending}
        onSelect={() => logoutMutation.mutate()}
      >
        {t('common.signOut')}
      </DropdownItem>
    </Dropdown>
  );
}
