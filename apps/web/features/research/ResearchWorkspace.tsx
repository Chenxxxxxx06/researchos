'use client';

import { BookOpen, CalendarClock, Inbox, PanelLeftClose, PanelLeftOpen, PanelRightClose, PanelRightOpen, Search } from 'lucide-react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useI18n } from '@/lib/i18n';
import { useProjectAgentEvents } from '@/lib/websocket/useProjectAgentEvents';

import { PaperLibrary } from './PaperLibrary';
import { ResearchChat } from './chat/ResearchChat';
import { FeedTab } from './feed/FeedTab';
import { IdeaPanel } from './ideas/IdeaPanel';
import { SearchPanel } from './search/SearchPanel';

type RightTab = 'discover' | 'feed';

export function ResearchWorkspace({ projectId }: { projectId: string }) {
  const { t, locale } = useI18n();
  const zh = locale === 'zh-CN';
  const params = useSearchParams();
  const [tab, setTab] = useState<RightTab>(params.get('focus') === 'feed' ? 'feed' : 'discover');
  const [libraryOpen, setLibraryOpen] = useState(true);
  const [discoveryOpen, setDiscoveryOpen] = useState(true);
  const { runs, trackRun } = useProjectAgentEvents(projectId);

  return (
    <div className="-m-5 flex h-[calc(100dvh-4rem)] min-h-0 flex-col lg:-m-6 xl:-m-8">
      <header className="workspace-toolbar flex h-12 shrink-0 items-center justify-between gap-3 px-3 sm:px-4">
        <div className="flex min-w-0 items-center gap-2">
          <div className="flex items-center gap-2 pr-2 text-sm font-semibold tracking-[-0.01em] text-text">
            <Search className="h-4 w-4 text-accent" aria-hidden="true" />
            <span className="hidden sm:inline">{zh ? '资料与证据' : 'Evidence workspace'}</span>
          </div>
          <nav className="hidden items-center gap-1 border-l border-border pl-2 md:flex" aria-label={zh ? '资料工具' : 'Evidence tools'}>
            <QuickLink href={`/projects/${projectId}/inbox`} icon={Inbox} label={zh ? '收件箱' : 'Inbox'} />
            <QuickLink href={`/projects/${projectId}/references`} icon={BookOpen} label={zh ? '文献中心' : 'Library'} />
            <QuickLink href={`/projects/${projectId}/deadlines`} icon={CalendarClock} label="DDL" />
          </nav>
        </div>
        <div className="hidden items-center gap-1 xl:flex">
          <Button size="icon" variant="ghost" onClick={() => setLibraryOpen((value) => !value)} title={zh ? '切换文库与想法' : 'Toggle library and ideas'}>
            {libraryOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          </Button>
          <Button size="icon" variant="ghost" onClick={() => setDiscoveryOpen((value) => !value)} title={zh ? '切换论文发现' : 'Toggle discovery'}>
            {discoveryOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
          </Button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {libraryOpen && (
          <aside className="hidden w-[17rem] shrink-0 flex-col overflow-hidden border-r border-border bg-surface xl:flex">
            <div className="min-h-0 flex-1 overflow-y-auto p-3">
              <PaperLibrary projectId={projectId} onFocusDiscover={() => setTab('discover')} />
            </div>
            <div className="max-h-[44%] shrink-0 overflow-y-auto border-t border-border p-3">
              <IdeaPanel projectId={projectId} runs={runs} trackRun={trackRun} />
            </div>
          </aside>
        )}

        <main className="flex min-w-0 flex-1 flex-col bg-bg">
          <ResearchChat projectId={projectId} runs={runs} trackRun={trackRun} onFocusDiscover={() => setTab('discover')} />
        </main>

        {discoveryOpen && (
          <aside className="hidden w-[21rem] shrink-0 flex-col overflow-hidden border-l border-border bg-surface p-3 xl:flex 2xl:w-[23rem]">
            <Tabs value={tab} onValueChange={(value) => setTab(value as RightTab)} className="flex min-h-0 flex-1 flex-col">
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
        )}
      </div>
    </div>
  );
}

function QuickLink({ href, icon: Icon, label }: { href: string; icon: typeof Inbox; label: string }) {
  return (
    <Link href={href} className="inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-xs font-medium text-muted hover:bg-surface-2 hover:text-text">
      <Icon className="h-3.5 w-3.5" aria-hidden="true" />{label}
    </Link>
  );
}
