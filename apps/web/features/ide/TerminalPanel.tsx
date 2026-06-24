'use client';

/**
 * Terminal panel — UI/log shell only. It does NOT execute any commands
 * (PHASE3-D11). Real execution arrives with the runtime in a later phase.
 */
export function TerminalPanel() {
  return (
    <div className="flex h-full flex-col bg-neutral-900 font-mono text-xs text-neutral-200">
      <div className="flex items-center justify-between border-b border-neutral-700 px-3 py-1">
        <span className="text-neutral-400">TERMINAL</span>
        <span className="rounded bg-neutral-700 px-2 py-0.5 text-[10px] text-neutral-300">
          read-only · no execution
        </span>
      </div>
      <div className="flex-1 overflow-auto p-3 leading-relaxed">
        <div className="text-neutral-500"># Terminal is a UI shell in this MVP.</div>
        <div className="text-neutral-500"># Command execution is disabled by design.</div>
        <div className="mt-2">
          <span className="text-green-400">researchos</span>
          <span className="text-neutral-500">:~/workspace$</span> <span className="animate-pulse">▋</span>
        </div>
      </div>
    </div>
  );
}
