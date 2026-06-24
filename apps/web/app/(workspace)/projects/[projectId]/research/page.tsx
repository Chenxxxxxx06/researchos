'use client';

import { use } from 'react';

import { IdeaPanel } from '@/features/research/IdeaPanel';
import { PaperLibrary } from '@/features/research/PaperLibrary';
import { PaperSearchPanel } from '@/features/research/PaperSearchPanel';
import { ResearchChat } from '@/features/research/ResearchChat';

export default function ResearchPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  return (
    <div className="grid h-[calc(100vh-7rem)] grid-cols-12 gap-4">
      {/* Left: library + ideas */}
      <aside className="col-span-3 space-y-4 overflow-y-auto">
        <PaperLibrary projectId={projectId} />
        <IdeaPanel projectId={projectId} />
      </aside>

      {/* Center: research chat */}
      <section className="col-span-6 rounded-lg border border-neutral-200 bg-neutral-50 p-4">
        <ResearchChat projectId={projectId} />
      </section>

      {/* Right: source search */}
      <aside className="col-span-3 overflow-y-auto">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Find papers
        </h3>
        <PaperSearchPanel projectId={projectId} />
      </aside>
    </div>
  );
}
