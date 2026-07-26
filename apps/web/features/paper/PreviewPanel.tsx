'use client';

/**
 * Compile preview v2 (partition: frontend-paper, Design E.2).
 *
 * Tabs: structural Preview (headings/paragraphs/math/figures/lists from
 * `preview_model`) and Diagnostics (errors first). Preview blocks and diagnostic
 * rows both jump the editor to their source line. Degrades to the legacy `<pre>`
 * dump when `preview_model` is absent.
 */

import { useState } from 'react';
import { AlertCircle, AlertTriangle } from 'lucide-react';

import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/ui/empty-state';
import type { CompileJob, PreviewBlock, PreviewSection } from '@/lib/api/documents';
import { useI18n } from '@/lib/i18n';

function BlockView({ block, onJump }: { block: PreviewBlock; onJump: (line: number) => void }) {
  const line = block.line;
  const jump = () => line && onJump(line);
  const cls = 'w-full cursor-pointer text-left hover:bg-surface-2 rounded px-1 -mx-1';

  if (block.kind === 'math') {
    return (
      <button type="button" onClick={jump} className={cls}>
        <pre className="overflow-x-auto rounded bg-surface-2 px-2 py-1 text-center font-mono text-xs text-text">
          {block.text}
        </pre>
      </button>
    );
  }
  if (block.kind === 'figure') {
    return (
      <button type="button" onClick={jump} className={cls}>
        <div className="rounded border border-dashed border-border px-2 py-3 text-center text-xs text-muted">
          🖼 {block.caption ?? block.name ?? 'figure'}
        </div>
      </button>
    );
  }
  if (block.kind === 'list' && block.items) {
    return (
      <button type="button" onClick={jump} className={cls}>
        <ul className="list-disc pl-5 text-xs text-text">
          {block.items.map((it, i) => (
            <li key={i}>{it}</li>
          ))}
        </ul>
      </button>
    );
  }
  return (
    <button type="button" onClick={jump} className={cls}>
      <p className="text-xs leading-relaxed text-text">{block.text}</p>
    </button>
  );
}

function SectionView({
  section,
  onJump,
}: {
  section: PreviewSection;
  onJump: (line: number) => void;
}) {
  const level = section.level ?? 1;
  const size = level <= 1 ? 'text-sm font-bold' : level === 2 ? 'text-xs font-semibold' : 'text-xs font-medium';
  return (
    <div className="space-y-1.5">
      {section.title && (
        <button
          type="button"
          onClick={() => section.line && onJump(section.line)}
          className={`block w-full rounded px-1 -mx-1 text-left text-text hover:bg-surface-2 ${size}`}
        >
          {section.number ? `${section.number} ` : ''}
          {section.title}
        </button>
      )}
      {(section.blocks ?? []).map((b, i) => (
        <BlockView key={i} block={b} onJump={onJump} />
      ))}
    </div>
  );
}

export function PreviewPanel({
  job,
  isCompiling,
  onJumpToLine,
}: {
  job: CompileJob | null;
  isCompiling: boolean;
  onJumpToLine: (line: number) => void;
}) {
  const { t } = useI18n();
  const [tab, setTab] = useState<'preview' | 'diagnostics'>('preview');

  const diagnostics = job?.diagnostics ?? [];
  const sortedDiags = [...diagnostics].sort((a, b) =>
    a.severity === b.severity ? a.line - b.line : a.severity === 'error' ? -1 : 1,
  );
  const sections = job?.preview_model?.sections ?? null;

  return (
    <div className="flex h-full flex-col">
      <Tabs value={tab} onValueChange={(v) => setTab(v as 'preview' | 'diagnostics')}>
        <TabsList className="px-3">
          <TabsTrigger value="preview">{t('paper.preview')}</TabsTrigger>
          <TabsTrigger value="diagnostics">
            {t('paper.diagnostics')}
            {diagnostics.length > 0 ? ` (${diagnostics.length})` : ''}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="preview" className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {isCompiling && !job ? (
            <Skeleton className="h-40 w-full" />
          ) : !job ? (
            <p className="pt-6 text-center text-xs text-faint">{t('paper.preview.empty')}</p>
          ) : sections ? (
            <div className="space-y-3">
              {job.preview_model?.title && (
                <h1 className="text-base font-bold text-text">{job.preview_model.title}</h1>
              )}
              {sections.map((s, i) => (
                <SectionView key={i} section={s} onJump={onJumpToLine} />
              ))}
            </div>
          ) : job.preview ? (
            <pre className="whitespace-pre-wrap text-xs leading-relaxed text-text">{job.preview}</pre>
          ) : (
            <p className="pt-6 text-center text-xs text-faint">{t('paper.preview.empty')}</p>
          )}
        </TabsContent>

        <TabsContent value="diagnostics" className="min-h-0 flex-1 overflow-y-auto px-3 pb-4">
          {sortedDiags.length === 0 ? (
            <EmptyState title={t('paper.diagnostics.empty')} className="border-0" />
          ) : (
            <ul className="space-y-1">
              {sortedDiags.map((d, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => onJumpToLine(d.line)}
                    className="flex w-full items-start gap-2 rounded px-1 py-1 text-left hover:bg-surface-2"
                  >
                    {d.severity === 'error' ? (
                      <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" aria-hidden="true" />
                    ) : (
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warn" aria-hidden="true" />
                    )}
                    <span className="min-w-0">
                      <span className="font-mono text-[10px] text-muted">
                        {d.file}:{d.line}
                      </span>
                      <span className="block text-xs text-text">{d.message}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
