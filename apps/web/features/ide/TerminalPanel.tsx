'use client';

export function TerminalPanel() {
  return (
    <div className="flex h-full flex-col bg-[#1e1e1e] font-mono text-xs text-[#d4d4d4]">
      <div className="flex items-center gap-3 border-b border-[#333] px-4 py-1.5">
        <span className="text-[11px] font-medium text-[#888]">TERMINAL</span>
        <span className="rounded bg-[#333] px-2 py-0.5 text-[10px] text-[#888]">read‑only</span>
      </div>
      <div className="flex-1 overflow-auto px-4 py-3 leading-relaxed">
        <div className="text-[#6a6a6a]"># Terminal shell — command execution disabled by design.</div>
        <div className="mt-3"><span className="text-[#4ec9b0]">researchos</span> <span className="text-[#888]">~/workspace$</span> <span className="animate-pulse text-[#dcdcaa]">▋</span></div>
      </div>
    </div>
  );
}
