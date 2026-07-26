'use client';

/**
 * Keyboard cheatsheet (opened with `?`). Rendered FROM the command registry —
 * every registered command with a `shortcut` appears, so docs never drift.
 */

import { useMemo } from 'react';

import { useCommandStore, type Command, type CommandSection } from '@/lib/command/registry';
import { useI18n, type DictKey } from '@/lib/i18n';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Kbd } from '@/components/ui/kbd';

const SECTION_LABELS: Record<CommandSection, DictKey> = {
  navigate: 'palette.sectionNavigate',
  action: 'palette.sectionAction',
  theme: 'palette.sectionTheme',
  file: 'palette.sectionFile',
  paper: 'palette.sectionPaper',
  run: 'palette.sectionRun',
};

export function ShortcutCheatsheet() {
  const open = useCommandStore((s) => s.cheatsheetOpen);
  const setOpen = useCommandStore((s) => s.setCheatsheetOpen);
  const commands = useCommandStore((s) => s.commands);
  const { t } = useI18n();

  const sections = useMemo(() => {
    const bySection = new Map<CommandSection, Command[]>();
    for (const cmd of commands.values()) {
      if (!cmd.shortcut) continue;
      const bucket = bySection.get(cmd.section) ?? [];
      bucket.push(cmd);
      bySection.set(cmd.section, bucket);
    }
    return Array.from(bySection.entries());
  }, [commands]);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent size="md">
        <DialogHeader>
          <div>
            <DialogTitle>{t('shortcuts.title')}</DialogTitle>
            <DialogDescription>{t('shortcuts.pressG')}</DialogDescription>
          </div>
          <DialogClose />
        </DialogHeader>
        <div className="max-h-[60vh] space-y-4 overflow-y-auto p-4 pt-1">
          {sections.map(([section, cmds]) => (
            <div key={section}>
              <p className="mb-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
                {t(SECTION_LABELS[section])}
              </p>
              <ul className="space-y-1">
                {cmds.map((cmd) => (
                  <li key={cmd.id} className="flex items-center justify-between gap-4 text-sm">
                    <span className="truncate text-text">{cmd.title}</span>
                    <Kbd keys={cmd.shortcut!} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
