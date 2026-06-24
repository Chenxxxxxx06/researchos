export interface CitationLike { label: string; url?: string; }

export function CitationChip({ citation }: { citation: CitationLike }) {
  const inner = <span className="font-mono">{citation.label}</span>;
  const cls = "inline-block rounded bg-neutral-100 px-1.5 py-0.5 font-mono text-[10px] text-neutral-600 hover:bg-neutral-200 transition-colors";
  return citation.url ? <a href={citation.url} target="_blank" rel="noreferrer" className={cls + " underline decoration-neutral-300"}>{inner}</a> : <span className={cls}>{inner}</span>;
}
