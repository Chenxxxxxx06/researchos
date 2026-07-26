'use client';

/**
 * Static hunk renderer (D3.4): a `<table>` of old/new line numbers, a `+`/`−`
 * gutter, and token-colored rows via CSS only — no Monaco instance per hunk.
 */

import type { DisplayHunk } from '@/lib/ide/diff';

export function HunkView({ hunk }: { hunk: DisplayHunk }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-mono text-xs leading-5">
        <tbody>
          <tr className="select-none bg-surface-2 text-muted">
            <td colSpan={3} className="px-3 py-0.5 text-[11px]">
              {hunk.header}
            </td>
          </tr>
          {hunk.lines.map((line, i) => (
            <tr
              key={i}
              className={
                line.kind === 'add'
                  ? 'bg-success-bg'
                  : line.kind === 'del'
                    ? 'bg-danger-bg'
                    : undefined
              }
            >
              <td className="w-10 select-none border-r border-border px-2 text-right align-top text-faint tabular-nums">
                {line.oldNo ?? ''}
              </td>
              <td className="w-10 select-none border-r border-border px-2 text-right align-top text-faint tabular-nums">
                {line.newNo ?? ''}
              </td>
              <td
                className={
                  'whitespace-pre px-2 align-top ' +
                  (line.kind === 'add'
                    ? 'text-success'
                    : line.kind === 'del'
                      ? 'text-danger'
                      : 'text-text')
                }
              >
                <span className="select-none pr-1 text-faint">
                  {line.kind === 'add' ? '+' : line.kind === 'del' ? '-' : ' '}
                </span>
                {line.text.length > 0 ? line.text : ' '}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
