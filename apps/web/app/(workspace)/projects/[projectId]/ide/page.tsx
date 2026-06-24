'use client';

import { use } from 'react';

import { CodingAssistant } from '@/features/ide/CodingAssistant';
import { EditorPane } from '@/features/ide/EditorPane';
import { FileTree } from '@/features/ide/FileTree';
import { GitStatusPanel } from '@/features/ide/GitStatusPanel';
import { PatchReviewPanel } from '@/features/ide/PatchReviewPanel';
import { TerminalPanel } from '@/features/ide/TerminalPanel';

export default function IdePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = use(params);

  return (
    <div className="-m-6 flex h-[calc(100vh-3.5rem)] flex-col">
      <div className="flex min-h-0 flex-1">
        {/* Left: explorer + source control */}
        <aside className="flex w-56 shrink-0 flex-col overflow-y-auto border-r border-neutral-200 bg-white">
          <div className="flex-1 overflow-y-auto">
            <FileTree projectId={projectId} />
          </div>
          <GitStatusPanel projectId={projectId} />
        </aside>

        {/* Center: editor + terminal */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="min-h-0 flex-1">
            <EditorPane projectId={projectId} />
          </div>
          <div className="h-40 shrink-0 border-t border-neutral-200">
            <TerminalPanel />
          </div>
        </div>

        {/* Right: AI assistant + patch review */}
        <aside className="flex w-96 shrink-0 flex-col border-l border-neutral-200 bg-white">
          <CodingAssistant projectId={projectId} />
          <div className="min-h-0 flex-1">
            <PatchReviewPanel projectId={projectId} />
          </div>
        </aside>
      </div>
    </div>
  );
}
