'use client';

/**
 * Ctrl/Cmd+K command palette. Renders from the command registry plus
 * transient "Open project: …" entries derived from the ['projects'] query
 * cache at open time (read-only cache access; no feature coupling).
 */

import { useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { FolderOpen, SearchX } from 'lucide-react';

import { commandScore } from '@/lib/command/fuzzy';
import { useCommandStore, type Command, type CommandContext, type CommandSection } from '@/lib/command/registry';
import { useI18n, type DictKey } from '@/lib/i18n';
import { Dialog, DialogContent } from '@/components/ui/dialog';
import { Kbd } from '@/components/ui/kbd';
import { cn } from '@/lib/utils';

const SECTION_LABELS: Record<CommandSection, DictKey> = {
  navigate: 'palette.sectionNavigate',
  action: 'palette.sectionAction',
  theme: 'palette.sectionTheme',
  file: 'palette.sectionFile',
  paper: 'palette.sectionPaper',
  run: 'palette.sectionRun',
};

const MRU_KEY = 'ros-cmd-mru';
const MRU_BOOST = 15;
const PER_SECTION_LIMIT = 8;

function readMru(): string[] {
  try {
    const raw = window.localStorage.getItem(MRU_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [];
  } catch {
    return [];
  }
}

function pushMru(id: string): void {
  try {
    const next = [id, ...readMru().filter((x) => x !== id)].slice(0, 10);
    window.localStorage.setItem(MRU_KEY, JSON.stringify(next));
  } catch {
    // best-effort
  }
}

interface ProjectCacheItem {
  id: string;
  name: string;
}

export function CommandPalette() {
  const open = useCommandStore((s) => s.open);
  const setOpen = useCommandStore((s) => s.setOpen);
  const commands = useCommandStore((s) => s.commands);
  const { t } = useI18n();
  const router = useRouter();
  const params = useParams<{ projectId?: string }>();
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listboxId = 'ros-command-listbox';

  const ctx: CommandContext = useMemo(
    () => ({
      router: { push: (href: string) => router.push(href) },
      projectId: params?.projectId ?? null,
      queryClient,
      close: () => setOpen(false),
    }),
    [router, params?.projectId, queryClient, setOpen],
  );

  // Reset per open; focus lands on the input (autoFocus inside <dialog>).
  useEffect(() => {
    if (open) {
      setQuery('');
      setActiveIndex(0);
    }
  }, [open]);

  // Transient "Open project" commands from the query cache, read at open time.
  const projectCommands = useMemo<Command[]>(() => {
    if (!open) return [];
    const entries = queryClient.getQueriesData<{ items?: ProjectCacheItem[] }>({
      queryKey: ['projects'],
    });
    const seen = new Set<string>();
    const cmds: Command[] = [];
    for (const [, data] of entries) {
      for (const item of data?.items ?? []) {
        if (!item?.id || seen.has(item.id)) continue;
        seen.add(item.id);
        cmds.push({
          id: `nav.project.${item.id}`,
          title: t('palette.openProject', { name: item.name }),
          section: 'navigate',
          icon: FolderOpen,
          keywords: [item.name, 'project'],
          run: (c) => c.router.push(`/projects/${item.id}/overview`),
        });
      }
    }
    return cmds;
  }, [open, queryClient, t]);

  const groups = useMemo(() => {
    const all = [...commands.values(), ...projectCommands].filter(
      (cmd) => !cmd.enabled || cmd.enabled(ctx),
    );
    const mru = open && typeof window !== 'undefined' ? readMru() : [];
    const trimmed = query.trim();

    let visible: Command[];
    if (trimmed.length === 0) {
      visible = all;
    } else {
      visible = all
        .map((cmd) => ({ cmd, score: commandScore(trimmed, cmd) }))
        .filter((x): x is { cmd: Command; score: number } => x.score !== null)
        .map((x) => ({ cmd: x.cmd, score: x.score + (mru.includes(x.cmd.id) ? MRU_BOOST : 0) }))
        .sort((a, b) => b.score - a.score)
        .map((x) => x.cmd);
    }

    // Group by section, preserving first-appearance order; cap per section.
    const bySection = new Map<CommandSection, Command[]>();
    for (const cmd of visible) {
      const bucket = bySection.get(cmd.section) ?? [];
      if (bucket.length < PER_SECTION_LIMIT) bucket.push(cmd);
      bySection.set(cmd.section, bucket);
    }
    const flat: Command[] = [];
    const sections = Array.from(bySection.entries()).map(([section, cmds]) => {
      const startIndex = flat.length;
      flat.push(...cmds);
      return { section, cmds, startIndex };
    });
    return { sections, flat };
  }, [commands, projectCommands, ctx, query, open]);

  const active = groups.flat[Math.min(activeIndex, groups.flat.length - 1)] ?? null;
  const activeId = active ? `ros-cmd-${active.id}` : undefined;

  useEffect(() => {
    if (activeId) document.getElementById(activeId)?.scrollIntoView({ block: 'nearest' });
  }, [activeId]);

  const runCommand = (cmd: Command) => {
    pushMru(cmd.id);
    setOpen(false);
    void cmd.run(ctx);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(groups.flat.length - 1, 0)));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (active) runCommand(active);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen} className="mt-[10vh] mb-auto">
      <DialogContent size="md" className="overflow-hidden p-0">
        <input
          ref={inputRef}
          data-autofocus=""
          role="combobox"
          aria-expanded="true"
          aria-controls={listboxId}
          aria-activedescendant={activeId}
          aria-label={t('palette.hint')}
          placeholder={t('palette.placeholder')}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setActiveIndex(0);
          }}
          onKeyDown={onKeyDown}
          className="h-12 w-full border-b border-border bg-transparent px-4 text-sm text-text placeholder:text-faint focus:outline-none"
        />
        <div id={listboxId} role="listbox" aria-label={t('palette.hint')} className="max-h-[50vh] overflow-y-auto p-1.5">
          {groups.flat.length === 0 && (
            <div className="flex flex-col items-center gap-1.5 py-8 text-center">
              <SearchX className="h-5 w-5 text-faint" aria-hidden="true" />
              <p className="text-sm text-muted">{t('palette.empty')}</p>
            </div>
          )}
          {groups.sections.map(({ section, cmds, startIndex }) => (
            <div key={section} className="mb-1">
              <div className="px-2.5 pb-0.5 pt-1.5 text-[11px] font-medium uppercase tracking-wide text-faint">
                {t(SECTION_LABELS[section])}
              </div>
              {cmds.map((cmd, offset) => {
                const index = startIndex + offset;
                const isActive = index === activeIndex;
                const Icon = cmd.icon;
                return (
                  <div
                    key={cmd.id}
                    id={`ros-cmd-${cmd.id}`}
                    role="option"
                    aria-selected={isActive}
                    onMouseEnter={() => setActiveIndex(index)}
                    onMouseDown={(e) => e.preventDefault()}
                    onClick={() => runCommand(cmd)}
                    className={cn(
                      'flex cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 text-sm',
                      isActive ? 'bg-surface-2 text-text' : 'text-text',
                    )}
                  >
                    {Icon ? (
                      <Icon className="h-4 w-4 shrink-0 text-muted" />
                    ) : (
                      <span className="h-4 w-4 shrink-0" />
                    )}
                    <span className="flex-1 truncate">{cmd.title}</span>
                    {cmd.shortcut && <Kbd keys={cmd.shortcut} />}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
