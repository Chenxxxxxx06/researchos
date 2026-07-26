'use client';

/**
 * One collapsible file section inside a diff card or commit diff. Renders a
 * resolved `FileDiffModel` (client-computed, server hunks, or whole-file) — it
 * never re-diffs against the live file. Reused by DiffCard and CommitDiffViewer.
 */

import { ChevronDown, ChevronRight, FileCode2, Maximize2 } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import type { FileDiffModel } from '@/lib/ide/diff';
import { useI18n } from '@/lib/i18n';
import type { DictKey } from '@/lib/i18n';

import { HunkView } from './HunkView';

export interface FileDiffSectionProps {
  path: string;
  changeType: string;
  model: FileDiffModel;
  defaultCollapsed?: boolean;
  selectable?: boolean;
  selected?: boolean;
  onToggleSelected?: () => void;
  onOpenAtLine?: (line: number) => void;
  onOpenFullDiff?: () => void;
}

const CHANGE_LABEL: Record<string, DictKey> = {
  create: 'ide.changeCreate',
  added: 'ide.changeAdded',
  modify: 'ide.changeModify',
  modified: 'ide.changeModify',
  delete: 'ide.changeDelete',
  deleted: 'ide.changeDelete',
  renamed: 'ide.changeRenamed',
};

function changeVariant(changeType: string): 'success' | 'danger' | 'info' | 'neutral' {
  if (changeType === 'create' || changeType === 'added') return 'success';
  if (changeType === 'delete' || changeType === 'deleted') return 'danger';
  if (changeType === 'renamed') return 'neutral';
  return 'info';
}

export function FileDiffSection({
  path,
  changeType,
  model,
  defaultCollapsed = false,
  selectable = false,
  selected = true,
  onToggleSelected,
  onOpenAtLine,
  onOpenFullDiff,
}: FileDiffSectionProps) {
  const { t } = useI18n();
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const labelKey = CHANGE_LABEL[changeType];
  const firstLine = model.hunks[0]?.newStart ?? 1;

  return (
    <div className="border-t border-border first:border-t-0">
      <div className="flex items-center gap-2 px-2 py-1.5">
        {selectable && (
          <input
            type="checkbox"
            aria-label={path}
            checked={selected}
            onChange={onToggleSelected}
            className="h-3.5 w-3.5 shrink-0 rounded border-border-strong"
          />
        )}
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          className="flex min-w-0 flex-1 items-center gap-1.5 text-left outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
        >
          {collapsed ? (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
          )}
          <FileCode2 className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
          <span className="truncate font-mono text-xs text-text" title={path}>
            {path}
          </span>
          {labelKey && (
            <Badge variant={changeVariant(changeType)} size="sm">
              {t(labelKey)}
            </Badge>
          )}
        </button>
        <span className="shrink-0 font-mono text-[11px]">
          <span className="text-success">+{model.additions}</span>{' '}
          <span className="text-danger">-{model.deletions}</span>
        </span>
        {onOpenAtLine && (
          <button
            type="button"
            onClick={() => onOpenAtLine(firstLine)}
            className="shrink-0 rounded p-1 text-muted hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
            aria-label={t('ide.openAtLine')}
            title={t('ide.openAtLine')}
          >
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
        {onOpenFullDiff && (
          <button
            type="button"
            onClick={onOpenFullDiff}
            className="shrink-0 rounded p-1 text-muted hover:bg-surface-2 hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
            aria-label={t('ide.openFullDiff')}
            title={t('ide.openFullDiff')}
          >
            <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        )}
      </div>

      {!collapsed && (
        <div className="border-t border-border">
          {model.tooLarge ? (
            <div className="flex items-center justify-between gap-2 px-3 py-3 text-xs text-muted">
              <span>{t('ide.diffTooLarge')}</span>
              {onOpenFullDiff && (
                <button
                  type="button"
                  onClick={onOpenFullDiff}
                  className="font-medium text-info hover:underline"
                >
                  {t('ide.openFullDiff')}
                </button>
              )}
            </div>
          ) : model.hunks.length === 0 ? (
            <div className="px-3 py-2 text-xs text-muted">{t('ide.noDiff')}</div>
          ) : (
            model.hunks.map((hunk, i) => <HunkView key={i} hunk={hunk} />)
          )}
        </div>
      )}
    </div>
  );
}
