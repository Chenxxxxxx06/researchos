'use client';

import { useSearchParams } from 'next/navigation';
import { useState } from 'react';

import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

import { PaperLibrary } from './PaperLibrary';
import { ResearchChat } from './chat/ResearchChat';
import { FeedTab } from './feed/FeedTab';
import { IdeaPanel } from './ideas/IdeaPanel';
import { SearchPanel } from './search/SearchPanel';

type RightTab = 'discover' | 'feed';

/**
 * Research workspace shell (D1). Owns the right-rail Discover/Feed tab (deep-
 * linkable via `?focus=feed|search`) and mounts a SINGLE `useProjectAgentEvents`
 * whose `runs`/`trackRun` are fanned out to the chat and ideas panels — fixing
 * the one-socket-per-component leak. Paper-ingest / feed live updates degrade to
 * the per-panel polling fallbacks (the generic `useProjectEvents` hook was not
 * shipped by frontend-ide — see NOTES-FOR-GATE).
 */
export function ResearchWorkspace({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const params = useSearchParams();
  const [tab, setTab] = useState<RightTab>(params.get('focus') === 'feed' ? 'feed' : 'discover');
  const { runs, trackRun } = useProjectAgentEvents(projectId);

  const focusDiscover = () => setTab('discover');

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)]">
      <aside className="flex w-64 shrink-0 flex-col overflow-hidden border-r border-border bg-surface">
        <div className="flex-1 overflow-y-auto p-3">
          <PaperLibrary projectId={projectId} onFocusDiscover={focusDiscover} />
        </div>
        <div className="shrink-0 overflow-y-auto border-t border-border p-3" style={{ maxHeight: '48%' }}>
          <IdeaPanel projectId={projectId} runs={runs} trackRun={trackRun} />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col bg-bg">
        <ResearchChat projectId={projectId} runs={runs} trackRun={trackRun} onFocusDiscover={focusDiscover} />
      </div>

      <aside className="flex w-80 shrink-0 flex-col overflow-hidden border-l border-border bg-surface p-3">
        <Tabs value={tab} onValueChange={(v) => setTab(v as RightTab)} className="flex min-h-0 flex-1 flex-col">
          <TabsList>
            <TabsTrigger value="discover">{t('research.tabs.discover')}</TabsTrigger>
            <TabsTrigger value="feed">{t('research.tabs.feed')}</TabsTrigger>
          </TabsList>
          <TabsContent value="discover" className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <SearchPanel projectId={projectId} />
          </TabsContent>
          <TabsContent value="feed" className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <FeedTab projectId={projectId} />
          </TabsContent>
        </Tabs>
      </aside>
    </div>
  );
}
