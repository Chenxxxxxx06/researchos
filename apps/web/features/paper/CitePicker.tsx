'use client';

/**
 * Citation picker (partition: frontend-paper, Design F / SHOULD).
 *
 * Lists the project library + refs.bib entries (GET /citations), filters, and
 * inserts `\cite{key}` at the cursor. Rows not yet in refs.bib show "Add & cite"
 * which calls POST /citations/insert (adds the BibTeX entry) then inserts the
 * returned snippet. Any 404 renders the "unavailable" state (retry:false).
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useMemo, useState } from 'react';
import { Quote } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/ui/empty-state';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { toast } from '@/components/ui/toast';
import {
  insertCitation,
  listCitations,
  type CitationItem,
} from '@/lib/api/documents';
import { useI18n } from '@/lib/i18n';

export function CitePicker({
  projectId,
  latexProjectId,
  onInsert,
}: {
  projectId: string;
  latexProjectId: string;
  onInsert: (snippet: string) => void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [filter, setFilter] = useState('');

  const citations = useQuery({
    queryKey: ['citations', projectId, latexProjectId],
    queryFn: () => listCitations(projectId, latexProjectId, { limit: 100 }),
    retry: false,
  });

  const add = useMutation({
    mutationFn: (paperId: string) =>
      insertCitation(projectId, latexProjectId, { paper_id: paperId }),
    onSuccess: (res) => {
      onInsert(res.snippet);
      qc.invalidateQueries({ queryKey: ['citations', projectId, latexProjectId] });
      toast({ title: t('paper.cite.inserted', { key: res.cite_key }) });
    },
  });

  const filtered = useMemo(() => {
    const items = citations.data?.items ?? [];
    const q = filter.trim().toLowerCase();
    if (!q) return items;
    return items.filter(
      (c) =>
        c.cite_key.toLowerCase().includes(q) ||
        c.title.toLowerCase().includes(q) ||
        c.authors.some((a) => a.toLowerCase().includes(q)),
    );
  }, [citations.data, filter]);

  if (citations.isLoading) return <Skeleton className="h-40 w-full" />;
  if (citations.isError) return <EmptyState icon={Quote} title={t('paper.cite.unavailable')} />;

  const items = citations.data?.items ?? [];
  if (items.length === 0)
    return (
      <EmptyState icon={Quote} title={t('paper.cite.empty')} body={t('paper.cite.emptyBody')} />
    );

  const cite = (c: CitationItem) => {
    if (c.in_bib) {
      onInsert(`\\cite{${c.cite_key}}`);
      toast({ title: t('paper.cite.inserted', { key: c.cite_key }) });
    } else {
      add.mutate(c.paper_id);
    }
  };

  return (
    <div className="space-y-2">
      <Input
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder={t('paper.cite.filter')}
        className="h-8"
      />
      <ul className="space-y-1.5">
        {filtered.map((c) => (
          <li key={c.paper_id} className="rounded-md border border-border bg-surface p-2.5">
            <div className="flex items-center justify-between gap-2">
              <code className="truncate font-mono text-xs text-accent">{c.cite_key}</code>
              {c.in_bib && (
                <Badge variant="success" size="sm">
                  {t('paper.cite.inBib')}
                </Badge>
              )}
            </div>
            <p className="mt-0.5 line-clamp-2 text-xs text-text">{c.title}</p>
            <div className="mt-1 flex items-center justify-between gap-2">
              <span className="truncate text-[11px] text-muted">
                {c.authors.slice(0, 3).join(', ')}
                {c.year ? ` · ${c.year}` : ''}
              </span>
              <Button
                size="sm"
                variant={c.in_bib ? 'ghost' : 'secondary'}
                onClick={() => cite(c)}
                loading={add.isPending && add.variables === c.paper_id}
              >
                {c.in_bib ? t('paper.cite.insert') : t('paper.cite.addCite')}
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
