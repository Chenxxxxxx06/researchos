'use client';

/** Reconnection pill (D9): hidden when the socket is open. */

import { Loader2, WifiOff } from 'lucide-react';

import { useI18n } from '@/lib/i18n';
import { useProjectConnection } from '@/lib/websocket/useProjectAgentEvents';

export function ConnectionStatusPill({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const status = useProjectConnection(projectId);

  if (status.state === 'open' || status.state === 'closed') return null;

  const offline = status.state === 'offline';
  const label = offline
    ? t('ide.offline')
    : status.state === 'connecting'
      ? t('ide.connecting')
      : t('ide.reconnecting', { attempt: status.attempt });

  return (
    <div className="pointer-events-none absolute bottom-3 right-3 z-20 flex items-center gap-2 rounded-full border border-border bg-overlay px-3 py-1.5 text-xs text-muted shadow-elev2">
      {offline ? (
        <WifiOff className="h-3.5 w-3.5 text-warn" aria-hidden="true" />
      ) : (
        <Loader2 className="h-3.5 w-3.5 animate-spin text-warn" aria-hidden="true" />
      )}
      <span>{label}</span>
    </div>
  );
}
