'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useRouter } from 'next/navigation';

import { logout, type MeResponse } from '@/lib/api/auth';
import { useI18n } from '@/lib/i18n';
import { Button } from '@/components/ui/button';

import { LanguageSwitcher } from './LanguageSwitcher';
import { OrgSwitcher } from './OrgSwitcher';

export function TopBar({ me }: { me: MeResponse }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const { t } = useI18n();

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear();
      router.push('/login');
      router.refresh();
    },
  });

  return (
    <header className="flex h-14 items-center justify-between border-b border-neutral-200 bg-white px-4">
      <div className="flex items-center gap-3">
        <span className="text-sm font-bold tracking-tight">{t('app.name')}</span>
        <OrgSwitcher organizations={me.organizations} />
      </div>
      <div className="flex items-center gap-3">
        <LanguageSwitcher />
        <span className="text-sm text-neutral-600">{me.user.display_name}</span>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => logoutMutation.mutate()}
          disabled={logoutMutation.isPending}
        >
          {t('common.signOut')}
        </Button>
      </div>
    </header>
  );
}
