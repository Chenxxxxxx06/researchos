/**
 * Range conversions between the backend 1-based DocRange and Monaco (partition:
 * frontend-paper). `monaco-editor` is imported for TYPES ONLY (never at runtime).
 */

import type { editor, IRange, ISelection } from 'monaco-editor';

import type { DocRange } from '@/lib/api/documents';

/** Backend {start:{line,col}, end:{line,col}} → Monaco IRange (both 1-based). */
export function docRangeToMonaco(r: DocRange): IRange {
  return {
    startLineNumber: r.start.line,
    startColumn: r.start.col,
    endLineNumber: r.end.line,
    endColumn: r.end.col,
  };
}

/** Monaco selection → backend DocRange. */
export function selectionToDocRange(sel: ISelection): DocRange {
  return {
    start: { line: sel.selectionStartLineNumber, col: sel.selectionStartColumn },
    end: { line: sel.positionLineNumber, col: sel.positionColumn },
  };
}

/** True when the selection spans no characters. */
export function isEmptySelection(sel: ISelection): boolean {
  return (
    sel.selectionStartLineNumber === sel.positionLineNumber &&
    sel.selectionStartColumn === sel.positionColumn
  );
}

/** Read the model text covered by a DocRange (empty string when out of bounds). */
export function textInDocRange(model: editor.ITextModel, r: DocRange): string {
  try {
    return model.getValueInRange(docRangeToMonaco(r));
  } catch {
    return '';
  }
}
