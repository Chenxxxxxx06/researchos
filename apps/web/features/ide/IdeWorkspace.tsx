'use client';

/**
 * IDE layout (D9). Owns the whole grid so the route page is a one-liner. Left
 * rail: Explorer / Search + a source-control entry. Center: editor + terminal.
 * Right rail: Chat / Timeline switched by the store's `rightTab`. A beforeunload
 * guard warns on hard unloads while any buffer is dirty; the connection pill
 * surfaces socket reconnects.
 */

import { GitBranch } from 'lucide-react';
import { useEffect, useState } from 'react';

import { useIdeStore, type RightTab } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

import { ConnectionStatusPill } from './ConnectionStatusPill';
import { EditorPane } from './EditorPane';
import { FileTree } from './FileTree';
import { StatusHeader } from './GitStatusPanel';
import { SearchPanel } from './SearchPanel';
import { TerminalPanel } from './TerminalPanel';
import { CodingChat } from './chat/CodingChat';
import { GitTimelinePanel } from './git/GitTimelinePanel';

type LeftTab = 'explorer' | 'search';

function RailTab({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cn(
        '-mb-px flex-1 border-b-2 px-3 py-2 text-sm font-medium outline-none transition-colors',
        'focus-visible:ring-2 focus-visible:ring-focus/60',
        active ? 'border-accent text-text' : 'border-transparent text-muted hover:text-text',
      )}
    >
      {children}
    </button>
  );
}

export function IdeWorkspace({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const rightTab = useIdeStore((s) => s.rightTab);
  const setRightTab = useIdeStore((s) => s.setRightTab);
  const buffers = useIdeStore((s) => s.buffers);

  const [leftTab, setLeftTab] = useState<LeftTab>('explorer');
  const [searchSupported, setSearchSupported] = useState(true);

  // Warn on hard unloads while any buffer is dirty (SPA route changes keep tabs).
  useEffect(() => {
    if (Object.keys(buffers).length === 0) {
      window.onbeforeunload = null;
      return;
    }
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = '';
      return '';
    };
    window.onbeforeunload = handler;
    return () => {
      window.onbeforeunload = null;
    };
  }, [buffers]);

  return (
    <div className="relative -m-6 flex h-[calc(100vh-3.5rem)] flex-col">
      <div className="flex min-h-0 flex-1">
        {/* Left rail */}
        <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
          <div className="flex border-b border-border">
            <RailTab active={leftTab === 'explorer'} onClick={() => setLeftTab('explorer')}>
              {t('ide.explorer')}
            </RailTab>
            {searchSupported && (
              <RailTab active={leftTab === 'search'} onClick={() => setLeftTab('search')}>
                {t('ide.search')}
              </RailTab>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {leftTab === 'search' && searchSupported ? (
              <SearchPanel
                projectId={projectId}
                onUnsupported={() => {
                  setSearchSupported(false);
                  setLeftTab('explorer');
                }}
              />
            ) : (
              <FileTree projectId={projectId} />
            )}
          </div>

          <div className="shrink-0">
            <button
              type="button"
              onClick={() => setRightTab('git')}
              className="flex w-full items-center gap-1.5 border-t border-border px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-muted hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
            >
              <GitBranch className="h-3.5 w-3.5" aria-hidden="true" />
              {t('ide.sourceControl')}
            </button>
            <StatusHeader projectId={projectId} />
          </div>
        </aside>

        {/* Center */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <EditorPane projectId={projectId} />
          </div>
          <div className="h-40 shrink-0 border-t border-border">
            <TerminalPanel projectId={projectId} />
          </div>
        </div>

        {/* Right rail */}
        <aside className="flex w-[26rem] shrink-0 flex-col border-l border-border bg-surface">
          <div className="flex border-b border-border">
            <RailTab active={rightTab === 'chat'} onClick={() => setRightTab('chat')}>
              {t('ide.chat')}
            </RailTab>
            <RailTab active={rightTab === 'git'} onClick={() => setRightTab('git' as RightTab)}>
              {t('ide.timeline')}
            </RailTab>
          </div>
          <div className="min-h-0 flex-1">
            {rightTab === 'chat' ? (
              <CodingChat projectId={projectId} />
            ) : (
              <GitTimelinePanel projectId={projectId} />
            )}
          </div>
        </aside>
      </div>

      <ConnectionStatusPill projectId={projectId} />
    </div>
  );
}
