export interface CitationLike {
  label: string;
  url?: string;
}

export function CitationChip({ citation }: { citation: CitationLike }) {
  const content = <span className="font-mono">{citation.label}</span>;
  return citation.url ? (
    <a
      href={citation.url}
      target="_blank"
      rel="noreferrer"
      className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700 underline"
    >
      {content}
    </a>
  ) : (
    <span className="rounded bg-neutral-100 px-2 py-0.5 text-xs text-neutral-700">{content}</span>
  );
}
