'use client';

import { useQuery } from '@tanstack/react-query';
import { Bot, LockKeyhole, Wrench } from 'lucide-react';
import { useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { listAgentCapabilities } from '@/lib/api/agents';

export function AgentCapabilityLedger({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false);
  const capabilities = useQuery({
    queryKey: ['agent-capabilities', projectId],
    queryFn: () => listAgentCapabilities(projectId),
    staleTime: 5 * 60_000,
  });
  return (
    <section className="border-b border-border bg-bg">
      <div className="flex flex-wrap items-center justify-between gap-3 px-5 py-3">
        <div className="flex items-center gap-3"><Bot className="h-4 w-4 text-accent" /><div><h2 className="text-xs font-semibold text-text">Agent capability ledger</h2><p className="mt-0.5 text-[10px] text-muted">{capabilities.data?.length ?? 0} typed roles · explicit tools · explicit approval boundaries</p></div></div>
        <Button size="sm" variant="ghost" onClick={() => setOpen((value) => !value)}>{open ? 'Hide controls' : 'Inspect every agent'}</Button>
      </div>
      {open && (
        <div className="grid gap-px border-t border-border bg-border md:grid-cols-2 xl:grid-cols-4">
          {(capabilities.data ?? []).map((item) => <article key={item.agent_type} className="bg-surface p-4"><div className="flex items-start justify-between gap-2"><div><p className="text-xs font-semibold text-text">{item.role}</p><p className="mt-0.5 font-mono text-[9px] text-faint">{item.agent_type}</p></div><Badge size="sm" variant={item.status === 'ready' ? 'success' : 'warn'}>{item.status}</Badge></div><p className="mt-2 text-[10px] leading-4 text-muted">{item.purpose}</p><div className="mt-3 space-y-1 border-t border-border pt-2 text-[9px] leading-4 text-faint"><p className="flex gap-1.5"><Wrench className="mt-0.5 h-2.5 w-2.5 shrink-0" />{item.tools.length ? item.tools.join(', ') : 'No direct tools'}</p><p className="flex gap-1.5"><LockKeyhole className="mt-0.5 h-2.5 w-2.5 shrink-0" />{item.approval_boundaries.join(' · ')}</p></div></article>)}
          {capabilities.isLoading && <div className="col-span-full h-28 animate-pulse bg-surface-2" />}
        </div>
      )}
    </section>
  );
}
