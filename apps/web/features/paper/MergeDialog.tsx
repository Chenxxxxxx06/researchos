'use client';

/**
 * Save-conflict merge dialog (partition: frontend-paper, Design A.2).
 *
 * Opened on a 409 `document_version_conflict`. Shows a Monaco diff (server vs
 * mine) and lets the user Keep mine (re-save at the server version), Take server
 * (adopt the server copy; local text is preserved in the conflict-backup draft
 * slot), or Cancel. Built on the design-system `Dialog` primitive — never a
 * hand-rolled modal (DESIGN_TOKENS §4).
 */

import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { MonacoDiff } from '@/components/editor/monaco';
import { useI18n } from '@/lib/i18n';

export interface MergeDialogState {
  server: string;
  serverVersion: number;
  mine: string;
  mineVersion: number;
}

export function MergeDialog({
  state,
  busy,
  onKeepMine,
  onTakeServer,
  onCancel,
}: {
  state: MergeDialogState | null;
  busy?: boolean;
  onKeepMine: () => void;
  onTakeServer: () => void;
  onCancel: () => void;
}) {
  const { t } = useI18n();
  const open = state !== null;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) onCancel(); }}>
      <DialogContent size="lg" className="flex max-h-[85vh] flex-col">
        <DialogHeader>
          <div>
            <DialogTitle>{t('paper.merge.title')}</DialogTitle>
            <p className="mt-1 font-mono text-xs text-muted">
              {t('paper.merge.subtitle', {
                mine: state?.mineVersion ?? 0,
                server: state?.serverVersion ?? 0,
              })}
            </p>
          </div>
        </DialogHeader>

        <div className="px-4">
          <p className="mb-2 text-sm text-muted">{t('paper.merge.body')}</p>
          <div className="flex items-center justify-between px-1 text-[11px] font-medium uppercase tracking-wide text-faint">
            <span>{t('paper.merge.server')}</span>
            <span>{t('paper.merge.mine')}</span>
          </div>
          <div className="h-[46vh] overflow-hidden rounded-md border border-border">
            {open && (
              <MonacoDiff
                height="100%"
                language="plaintext"
                original={state?.server ?? ''}
                modified={state?.mine ?? ''}
                options={{
                  readOnly: true,
                  renderSideBySide: true,
                  minimap: { enabled: false },
                  fontSize: 12,
                  scrollBeyondLastLine: false,
                }}
              />
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="ghost" size="sm" onClick={onCancel} disabled={busy}>
            {t('common.cancel')}
          </Button>
          <Button variant="secondary" size="sm" onClick={onTakeServer} disabled={busy}>
            {t('paper.merge.takeServer')}
          </Button>
          <Button size="sm" onClick={onKeepMine} loading={busy}>
            {t('paper.merge.keepMine')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
