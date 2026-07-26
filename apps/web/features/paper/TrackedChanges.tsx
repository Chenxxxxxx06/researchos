'use client';

/**
 * Tracked-changes renderer (partition: frontend-paper, Design B.5).
 *
 * Server-side suggestions (CONSOLIDATION §8) are drawn two ways: a Monaco
 * strikethrough decoration over the original range, and a card tray anchored to
 * the editor showing the word-level diff (server `spans`, wordDiff fallback), the
 * rationale, and Accept/Reject/Reveal. `monaco-editor` is TYPES ONLY.
 */

import type { editor } from 'monaco-editor';
import { useEffect, useMemo, useRef } from 'react';

import type { Suggestion, SuggestionOp, SuggestionSpan } from '@/lib/api/documents';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { useI18n, type DictKey } from '@/lib/i18n';

import { ensurePaperDecorationStyles } from './monacoStyles';
import { docRangeToMonaco } from './range';
import { wordDiff, type WordDiffSegment } from './wordDiff';

const OP_LABEL: Record<SuggestionOp, DictKey> = {
  rewrite: 'paper.ai.rewrite',
  expand: 'paper.ai.expand',
  condense: 'paper.ai.condense',
  fix_grammar: 'paper.ai.fix',
  continue_writing: 'paper.ai.continue',
  custom: 'paper.ai.more',
};

function spansToSegments(spans: SuggestionSpan[]): WordDiffSegment[] {
  const out: WordDiffSegment[] = [];
  for (const span of spans) {
    if (span.kind === 'equal') out.push({ kind: 'same', text: span.old });
    else if (span.kind === 'delete') out.push({ kind: 'del', text: span.old });
    else if (span.kind === 'insert') out.push({ kind: 'ins', text: span.new });
    else {
      if (span.old) out.push({ kind: 'del', text: span.old });
      if (span.new) out.push({ kind: 'ins', text: span.new });
    }
  }
  return out;
}

function DiffBody({ suggestion }: { suggestion: Suggestion }) {
  const segments = useMemo<WordDiffSegment[]>(
    () =>
      suggestion.spans.length
        ? spansToSegments(suggestion.spans)
        : wordDiff(suggestion.old_text, suggestion.new_text),
    [suggestion.spans, suggestion.old_text, suggestion.new_text],
  );
  return (
    <p className="whitespace-pre-wrap break-words text-xs leading-relaxed text-text">
      {segments.map((seg, i) => {
        if (seg.kind === 'same') return <span key={i}>{seg.text}</span>;
        if (seg.kind === 'del')
          return (
            <del key={i} className="text-danger no-underline line-through">
              {seg.text}
            </del>
          );
        return (
          <ins key={i} className="bg-success-bg text-success no-underline">
            {seg.text}
          </ins>
        );
      })}
    </p>
  );
}

export function TrackedChanges({
  editor,
  suggestions,
  pendingId,
  onAccept,
  onReject,
  onReveal,
}: {
  editor: editor.IStandaloneCodeEditor;
  suggestions: Suggestion[];
  pendingId?: string | null;
  onAccept: (s: Suggestion) => void;
  onReject: (s: Suggestion) => void;
  onReveal: (s: Suggestion) => void;
}) {
  const { t } = useI18n();
  const collectionRef = useRef<editor.IEditorDecorationsCollection | null>(null);

  useEffect(() => {
    ensurePaperDecorationStyles();
    collectionRef.current = editor.createDecorationsCollection();
    return () => {
      collectionRef.current?.clear();
      collectionRef.current = null;
    };
  }, [editor]);

  useEffect(() => {
    const collection = collectionRef.current;
    if (!collection) return;
    const decorations: editor.IModelDeltaDecoration[] = suggestions
      .filter((s) => s.old_text !== '')
      .map((s) => ({
        range: docRangeToMonaco(s.range),
        options: { inlineClassName: 'ros-strike', className: 'ros-suggest-range' },
      }));
    collection.set(decorations);
  }, [suggestions]);

  if (suggestions.length === 0) return null;

  return (
    <div className="pointer-events-none absolute right-3 top-3 z-20 flex w-80 max-w-[85%] flex-col gap-2">
      <div className="pointer-events-auto max-h-[70vh] space-y-2 overflow-y-auto">
        {suggestions.map((s) => {
          const busy = pendingId === s.id;
          return (
            <div
              key={s.id}
              className="rounded-lg border border-border bg-overlay p-3 shadow-elev2"
            >
              <div className="mb-1.5 flex items-center justify-between gap-2">
                <Badge variant="accent" size="sm">
                  {t(OP_LABEL[s.op])}
                </Badge>
                <button
                  type="button"
                  onClick={() => onReveal(s)}
                  className="text-[11px] text-muted underline-offset-2 hover:text-text hover:underline"
                >
                  {t('paper.tracked.reveal')}
                </button>
              </div>
              <DiffBody suggestion={s} />
              {s.rationale && <p className="mt-1.5 text-[11px] italic text-muted">{s.rationale}</p>}
              <div className="mt-2 flex justify-end gap-2">
                <Button variant="ghost" size="sm" onClick={() => onReject(s)} disabled={busy}>
                  {t('paper.tracked.reject')}
                </Button>
                <Button size="sm" onClick={() => onAccept(s)} loading={busy}>
                  {t('paper.tracked.accept')}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
