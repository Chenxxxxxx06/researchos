'use client';

import { use } from 'react';

import { IdeaPanel } from '@/features/research/IdeaPanel';
import { PaperLibrary } from '@/features/research/PaperLibrary';
import { PaperSearchPanel } from '@/features/research/PaperSearchPanel';
import { ResearchChat } from '@/features/research/ResearchChat';

export default function ResearchPage({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = use(params);
  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)]">
      <aside className="flex w-60 shrink-0 flex-col overflow-hidden border-r border-neutral-200 bg-white">
        <div className="flex-1 overflow-y-auto p-3"><PaperLibrary projectId={projectId} /></div>
        <div className="shrink-0 border-t border-neutral-200 overflow-y-auto p-3" style={{ maxHeight: '45%' }}><IdeaPanel projectId={projectId} /></div>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col bg-neutral-50"><ResearchChat projectId={projectId} /></div>
      <aside className="flex w-72 shrink-0 flex-col overflow-y-auto border-l border-neutral-200 bg-white p-3"><PaperSearchPanel projectId={projectId} /></aside>
    </div>
  );
}
