'use client';

import { useMutation } from '@tanstack/react-query';
import { Loader2, Play, ShieldCheck } from 'lucide-react';
import { useState } from 'react';

import { runTerminalCommand, type TerminalRunResult } from '@/lib/api/workspace';
import { runSSHCommand } from '@/lib/api/ssh';

type Entry = { command: string; result: TerminalRunResult };

function tokenize(command: string): string[] {
  const tokens: string[] = [];
  const pattern = /"([^"]*)"|'([^']*)'|([^\s]+)/g;
  for (const match of command.matchAll(pattern)) {
    tokens.push(match[1] ?? match[2] ?? match[3] ?? '');
  }
  return tokens;
}

export function TerminalPanel({ projectId, sshProfileId }: { projectId: string; sshProfileId?: string | null }) {
  const [command, setCommand] = useState('git status --short');
  const [entries, setEntries] = useState<Entry[]>([]);
  const run = useMutation({
    mutationFn: (value: string) =>
      sshProfileId
        ? runSSHCommand(projectId, sshProfileId, { argv: tokenize(value), cwd: '.' })
        : runTerminalCommand(projectId, { argv: tokenize(value), cwd: '.' }),
    onSuccess: (result, value) => {
      setEntries((current) => [...current.slice(-19), { command: value, result }]);
      setCommand('');
    },
  });

  const submit = () => {
    const value = command.trim();
    if (!value || run.isPending) return;
    run.mutate(value);
  };

  return (
    <div className="flex h-full flex-col bg-[#1e1e1e] font-mono text-xs text-[#d4d4d4]">
      <div className="flex items-center gap-3 border-b border-[#333] px-4 py-1.5">
        <span className="text-[11px] font-medium text-[#aaa]">TERMINAL</span>
        <span className="flex items-center gap-1 rounded bg-[#173d32] px-2 py-0.5 text-[10px] text-[#7ee2bd]">
          <ShieldCheck className="h-3 w-3" /> {sshProfileId ? 'SSH · host-key verified · audited' : 'local · real argv process · no shell'}
        </span>
        <span className="text-[10px] text-[#777]">
          python / pytest / node / pnpm / npm / read-only git
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-4 py-2 leading-relaxed">
        {entries.length === 0 && (
          <div className="text-[#777]">
            {sshProfileId
              ? 'Commands run in the configured remote workdir with an argv allowlist, timeout, and persisted audit record.'
              : 'Commands run in the real local project workspace. Staging and production reject this endpoint until an isolated runtime is configured.'}
          </div>
        )}
        {entries.map((entry, index) => (
          <div key={`${entry.command}-${index}`} className="mb-2">
            <div>
              <span className="text-[#4ec9b0]">{sshProfileId ? 'ssh' : 'researchos'}</span>{' '}
              <span className="text-[#888]">{entry.result.cwd}$</span>{' '}
              <span>{entry.command}</span>
            </div>
            {entry.result.stdout && (
              <pre className="whitespace-pre-wrap text-[#d4d4d4]">{entry.result.stdout}</pre>
            )}
            {entry.result.stderr && (
              <pre className="whitespace-pre-wrap text-[#f48771]">{entry.result.stderr}</pre>
            )}
            <div className="text-[10px] text-[#777]">
              exit {entry.result.exit_code ?? '—'} · {entry.result.duration_ms} ms
              {entry.result.timed_out ? ' · timed out' : ''}
            </div>
          </div>
        ))}
        {run.error && (
          <div className="mb-2 text-[#f48771]">
            {run.error instanceof Error ? run.error.message : 'Command failed'}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2 border-t border-[#333] px-3 py-1.5">
        <span className="text-[#4ec9b0]">{sshProfileId ? 'ssh' : 'researchos'}</span>
        <span className="text-[#888]">{sshProfileId ? 'remote$' : '~/workspace$'}</span>
        <input
          value={command}
          onChange={(event) => setCommand(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') submit();
          }}
          className="min-w-0 flex-1 bg-transparent text-[#d4d4d4] outline-none"
          aria-label="Terminal command"
        />
        <button
          type="button"
          onClick={submit}
          disabled={run.isPending}
          className="rounded p-1 text-[#aaa] hover:bg-[#333] hover:text-[#f0f0f0] disabled:opacity-50"
          aria-label="Run command"
        >
          {run.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Play className="h-3.5 w-3.5" />
          )}
        </button>
      </div>
    </div>
  );
}
