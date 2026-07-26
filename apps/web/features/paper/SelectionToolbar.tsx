'use client';

/**
 * Floating selection toolbar (partition: frontend-paper, Design B.1).
 *
 * A Monaco content widget anchored above the selection. Non-empty selection →
 * Rewrite/Expand/Condense/Fix/More; empty selection → Continue at the cursor.
 * Actions fire a server-side selection-op (CONSOLIDATION §8); the resulting
 * suggestion is rendered by TrackedChanges. `monaco-editor` is TYPES ONLY.
 */

import type { Monaco } from '@monaco-editor/react';
import type { editor, IDisposable, IPosition } from 'monaco-editor';
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

import type { DocRange, SuggestionOp } from '@/lib/api/documents';
import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

import { isEmptySelection, selectionToDocRange } from './range';

const WIDGET_ID = 'ros.paper.selection-toolbar';
const DEBOUNCE_MS = 150;

type OnAction = (
  op: SuggestionOp,
  range: DocRange,
  selectionText: string,
  instruction?: string,
) => void;

interface ActionButton {
  op: SuggestionOp;
  key: 'rewrite' | 'expand' | 'condense' | 'fix';
}

const SELECTION_ACTIONS: ActionButton[] = [
  { op: 'rewrite', key: 'rewrite' },
  { op: 'expand', key: 'expand' },
  { op: 'condense', key: 'condense' },
  { op: 'fix_grammar', key: 'fix' },
];

export function SelectionToolbar({
  editor,
  monaco,
  onAction,
  disabled,
}: {
  editor: editor.IStandaloneCodeEditor;
  monaco: Monaco;
  onAction: OnAction;
  disabled?: boolean;
}) {
  const { t } = useI18n();
  const [node] = useState<HTMLDivElement | null>(() =>
    typeof document !== 'undefined' ? document.createElement('div') : null,
  );
  const [visible, setVisible] = useState(false);
  const [mode, setMode] = useState<'selection' | 'cursor'>('selection');
  const [showCustom, setShowCustom] = useState(false);
  const [custom, setCustom] = useState('');

  // Captured at the moment the toolbar is shown (survives focus loss on click).
  const rangeRef = useRef<DocRange | null>(null);
  const textRef = useRef('');
  const positionRef = useRef<IPosition | null>(null);
  const visibleRef = useRef(false);
  visibleRef.current = visible;
  const widgetRef = useRef<editor.IContentWidget | null>(null);

  useEffect(() => {
    if (!node) return;
    node.style.zIndex = '30';

    const widget: editor.IContentWidget = {
      getId: () => WIDGET_ID,
      getDomNode: () => node,
      getPosition: () =>
        visibleRef.current && positionRef.current
          ? {
              position: positionRef.current,
              preference: [
                monaco.editor.ContentWidgetPositionPreference.ABOVE,
                monaco.editor.ContentWidgetPositionPreference.BELOW,
              ],
            }
          : null,
    };
    widgetRef.current = widget;
    editor.addContentWidget(widget);

    let timer: ReturnType<typeof setTimeout> | null = null;
    const disposables: IDisposable[] = [];

    const recompute = () => {
      const sel = editor.getSelection();
      const model = editor.getModel();
      if (!sel || !model) {
        setVisible(false);
        return;
      }
      const empty = isEmptySelection(sel);
      rangeRef.current = selectionToDocRange(sel);
      textRef.current = empty ? '' : model.getValueInRange(sel);
      positionRef.current = { lineNumber: sel.startLineNumber, column: sel.startColumn };
      setMode(empty ? 'cursor' : 'selection');
      setShowCustom(false);
      setVisible(true);
      editor.layoutContentWidget(widget);
    };

    disposables.push(
      editor.onDidChangeCursorSelection(() => {
        if (timer) clearTimeout(timer);
        timer = setTimeout(recompute, DEBOUNCE_MS);
      }),
    );
    disposables.push(
      editor.onDidScrollChange(() => {
        setVisible(false);
      }),
    );
    disposables.push(
      editor.onKeyDown((e) => {
        if (e.keyCode === monaco.KeyCode.Escape) setVisible(false);
      }),
    );

    return () => {
      if (timer) clearTimeout(timer);
      disposables.forEach((d) => d.dispose());
      editor.removeContentWidget(widget);
      widgetRef.current = null;
    };
  }, [editor, monaco, node]);

  // Re-query getPosition (reads refs) whenever visibility/size changes.
  useEffect(() => {
    if (widgetRef.current) editor.layoutContentWidget(widgetRef.current);
  }, [visible, mode, showCustom, editor]);

  if (!node) return null;

  const fire = (op: SuggestionOp, instruction?: string) => {
    if (disabled || !rangeRef.current) return;
    onAction(op, rangeRef.current, textRef.current, instruction);
    setVisible(false);
    setCustom('');
  };

  return createPortal(
    visible ? (
      <div
        className={cn(
          'mb-1 flex items-center gap-0.5 rounded-md border border-border bg-overlay p-1 shadow-elev2',
          disabled && 'pointer-events-none opacity-60',
        )}
        role="toolbar"
        onMouseDown={(e) => e.preventDefault()}
      >
        {mode === 'cursor' ? (
          <ToolbarButton label={t('paper.ai.continue')} onClick={() => fire('continue_writing')} />
        ) : showCustom ? (
          <form
            className="flex items-center gap-1"
            onSubmit={(e) => {
              e.preventDefault();
              if (custom.trim()) fire('custom', custom.trim());
            }}
          >
            <input
              autoFocus
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              placeholder={t('paper.ai.customPlaceholder')}
              className="h-7 w-56 rounded-sm border border-border-strong bg-surface px-2 text-xs text-text placeholder:text-faint focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
            />
            <ToolbarButton label="↵" onClick={() => custom.trim() && fire('custom', custom.trim())} />
          </form>
        ) : (
          <>
            {SELECTION_ACTIONS.map((a) => (
              <ToolbarButton key={a.op} label={t(`paper.ai.${a.key}`)} onClick={() => fire(a.op)} />
            ))}
            <ToolbarButton label={t('paper.ai.more')} onClick={() => setShowCustom(true)} />
          </>
        )}
      </div>
    ) : null,
    node,
  );
}

function ToolbarButton({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-sm px-2 py-1 text-xs font-medium text-text hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
    >
      {label}
    </button>
  );
}
