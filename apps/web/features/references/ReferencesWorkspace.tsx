'use client';

import { BookOpen, RefreshCw, Sparkles } from 'lucide-react';

import { PaperLibrary } from '@/features/research/PaperLibrary';
import { FeedTab } from '@/features/research/feed/FeedTab';

import { ZoteroConnectionPanel } from './ZoteroConnectionPanel';

export function ReferencesWorkspace({ projectId }: { projectId: string }) {
  return (
    <div className="-m-6 flex h-[calc(100vh-3rem)] min-h-0 flex-col">
      <header className="border-b border-border bg-surface px-6 py-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-text">
          <BookOpen className="h-5 w-5" /> 文献中心
        </h1>
        <p className="mt-1 text-sm text-muted">
          汇总 Zotero、项目文献库与个性化论文推送，作为创新分析和实验规划的证据来源。
        </p>
      </header>

      <div className="grid min-h-0 flex-1 grid-cols-[20rem_minmax(20rem,1fr)_minmax(24rem,1.15fr)]">
        <aside className="overflow-y-auto border-r border-border bg-bg p-4">
          <ZoteroConnectionPanel projectId={projectId} />
          <div className="mt-4 rounded-lg border border-border bg-surface p-3 text-xs text-muted">
            <div className="mb-1 flex items-center gap-1.5 font-medium text-text">
              <RefreshCw className="h-3.5 w-3.5" /> 推荐逻辑
            </div>
            同步后的标题、摘要和标签会形成你的研究兴趣画像。右侧论文按来源相关性、文库相似度和时间新鲜度联合排序。
          </div>
        </aside>

        <section className="min-h-0 overflow-y-auto border-r border-border bg-surface p-4">
          <div className="mb-3 flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-muted" />
            <h2 className="font-semibold text-text">项目参考文献</h2>
          </div>
          <PaperLibrary projectId={projectId} />
        </section>

        <section className="flex min-h-0 flex-col bg-bg p-4">
          <div className="mb-3 flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" />
            <h2 className="font-semibold text-text">为你推荐</h2>
          </div>
          <div className="min-h-0 flex-1">
            <FeedTab projectId={projectId} />
          </div>
        </section>
      </div>
    </div>
  );
}
