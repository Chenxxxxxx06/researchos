'use client';

/**
 * IDE layout (D9). Owns the whole grid so the route page is a one-liner. Left
 * rail: Explorer / Search + a source-control entry. Center: editor + terminal.
 * Right rail: Chat / Timeline switched by the store's `rightTab`. A beforeunload
 * guard warns on hard unloads while any buffer is dirty; the connection pill
 * surfaces socket reconnects.
 */

import { GitBranch, Server } from 'lucide-react';
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
import { RuntimeSwitcher } from './RuntimeSwitcher';
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

export function IdeWorkspace({
  projectId,
  initialSessionId = null,
}: {
  projectId: string;
  initialSessionId?: string | null;
}) {
  const { t } = useI18n();
  const rightTab = useIdeStore((s) => s.rightTab);
  const setRightTab = useIdeStore((s) => s.setRightTab);
  const buffers = useIdeStore((s) => s.buffers);
  const resetWorkspace = useIdeStore((s) => s.resetWorkspace);

  const [leftTab, setLeftTab] = useState<LeftTab>('explorer');
  const [searchSupported, setSearchSupported] = useState(true);
  const [sshProfileId, setSSHProfileId] = useState<string | null>(null);

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
    <div className="relative -m-6 flex h-[calc(100vh-3rem)] flex-col lg:-m-8">
      <RuntimeSwitcher
        projectId={projectId}
        profileId={sshProfileId}
        onChange={setSSHProfileId}
        onWorkspaceChange={() => {
          resetWorkspace();
          setLeftTab('explorer');
        }}
      />
      <div className="flex min-h-0 flex-1">
        {/* Left rail */}
        <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
          <div className="flex border-b border-border">
            <RailTab active={leftTab === 'explorer'} onClick={() => setLeftTab('explorer')}>
              {t('ide.explorer')}
            </RailTab>
            {searchSupported && !sshProfileId && (
              <RailTab active={leftTab === 'search'} onClick={() => setLeftTab('search')}>
                {t('ide.search')}
              </RailTab>
            )}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {leftTab === 'search' && searchSupported && !sshProfileId ? (
              <SearchPanel
                projectId={projectId}
                onUnsupported={() => {
                  setSearchSupported(false);
                  setLeftTab('explorer');
                }}
              />
            ) : (
              <FileTree projectId={projectId} sshProfileId={sshProfileId} />
            )}
          </div>

          {!sshProfileId && <div className="shrink-0">
            <button
              type="button"
              onClick={() => setRightTab('git')}
              className="flex w-full items-center gap-1.5 border-t border-border px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wider text-muted hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
            >
              <GitBranch className="h-3.5 w-3.5" aria-hidden="true" />
              {t('ide.sourceControl')}
            </button>
            <StatusHeader projectId={projectId} />
          </div>}
        </aside>

        {/* Center */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <EditorPane projectId={projectId} sshProfileId={sshProfileId} />
          </div>
          <div className="h-40 shrink-0 border-t border-border">
            <TerminalPanel projectId={projectId} sshProfileId={sshProfileId} />
          </div>
        </div>

        {/* Right rail */}
        {!sshProfileId ? <aside className="flex w-[26rem] shrink-0 flex-col border-l border-border bg-surface">
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
              <CodingChat projectId={projectId} initialSessionId={initialSessionId} />
            ) : (
              <GitTimelinePanel projectId={projectId} />
            )}
          </div>
        </aside> : <aside className="flex w-72 shrink-0 flex-col justify-center border-l border-border bg-surface p-6"><Server className="h-6 w-6 text-accent" /><h2 className="mt-4 text-sm font-semibold text-text">SSH 远程工作区</h2><p className="mt-2 text-xs leading-6 text-muted">当前文件通过 SFTP 直接读取和保存，终端命令具有超时、白名单和审计记录。Coding Agent 与 Git 补丁仍只作用于本地工作区，避免把未经审查的 Agent 写入直接发送到远端。</p></aside>}
      </div>

      <ConnectionStatusPill projectId={projectId} />
    </div>
  );
}
