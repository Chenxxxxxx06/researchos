'use client';

/** Session switcher + "New session" (hidden in fallback mode by CodingChat). */

import { ChevronDown, Plus } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Dropdown, DropdownItem } from '@/components/ui/dropdown';
import type { CodingSession } from '@/lib/api/codingAgent';
import { useI18n } from '@/lib/i18n';

export interface SessionBarProps {
  sessions: CodingSession[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  creating?: boolean;
}

export function SessionBar({ sessions, activeSessionId, onSelect, onNew, creating = false }: SessionBarProps) {
  const { t } = useI18n();
  const active = sessions.find((s) => s.id === activeSessionId);
  const label = active?.title || t('ide.session');

  return (
    <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-2">
      {sessions.length > 0 ? (
        <Dropdown
          align="start"
          panelClassName="max-h-64 overflow-y-auto"
          trigger={
            <Button variant="outline" size="sm" className="max-w-[12rem]">
              <span className="truncate">{label}</span>
              <ChevronDown className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            </Button>
          }
        >
          {sessions.map((s) => (
            <DropdownItem key={s.id} onSelect={() => onSelect(s.id)}>
              {s.title || t('ide.session')}
            </DropdownItem>
          ))}
        </Dropdown>
      ) : (
        <span className="text-sm font-medium text-text">{t('ide.codingChat')}</span>
      )}
      <Button variant="ghost" size="sm" onClick={onNew} loading={creating} className="ml-auto">
        {!creating && <Plus className="h-3.5 w-3.5" aria-hidden="true" />}
        {t('ide.newSession')}
      </Button>
    </div>
  );
}
