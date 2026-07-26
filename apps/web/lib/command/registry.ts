'use client';

/**
 * Extensible command registry (zustand). The palette, the shortcut layer, and
 * the cheatsheet all render from this single source of truth; feature specs
 * push their own commands via `registerCommand(s)` / `useRegisterCommands`
 * (worked example in docs/DESIGN_TOKENS.md §5).
 */

import { useEffect } from 'react';
import type { QueryClient } from '@tanstack/react-query';
import type { ComponentType } from 'react';
import { create } from 'zustand';

export type CommandSection = 'navigate' | 'action' | 'theme' | 'file' | 'paper' | 'run';

export interface CommandContext {
  router: { push(href: string): void };
  projectId: string | null;
  queryClient: QueryClient;
  /** Close the palette (no-op when invoked from the shortcut layer). */
  close(): void;
}

export interface Command {
  /** Unique id, e.g. 'nav.ide' or 'ide.save-active'. Re-registering replaces. */
  id: string;
  /** Already-localized title (registrants re-register on locale change). */
  title: string;
  section: CommandSection;
  keywords?: string[];
  icon?: ComponentType<{ className?: string }>;
  /** Chord ('mod+k') or sequence ('g i') — display + shortcut-layer binding. */
  shortcut?: string;
  /** Hidden from the palette and inert in the shortcut layer when false. */
  enabled?: (ctx: CommandContext) => boolean;
  run: (ctx: CommandContext) => void | Promise<void>;
}

interface CommandStore {
  commands: Map<string, Command>;
  open: boolean;
  cheatsheetOpen: boolean;
  setOpen: (open: boolean) => void;
  setCheatsheetOpen: (open: boolean) => void;
  register: (cmds: Command[]) => void;
  unregister: (ids: string[]) => void;
}

export const useCommandStore = create<CommandStore>((set) => ({
  commands: new Map<string, Command>(),
  open: false,
  cheatsheetOpen: false,
  setOpen: (open) => set({ open }),
  setCheatsheetOpen: (cheatsheetOpen) => set({ cheatsheetOpen }),
  register: (cmds) =>
    set((s) => {
      const next = new Map(s.commands);
      for (const cmd of cmds) {
        // Delete-then-set moves re-registrations to the end of the iteration
        // order so "last registration wins" holds for shortcut collisions.
        next.delete(cmd.id);
        next.set(cmd.id, cmd);
      }
      return { commands: next };
    }),
  unregister: (ids) =>
    set((s) => {
      const next = new Map(s.commands);
      for (const id of ids) next.delete(id);
      return { commands: next };
    }),
}));

/** Register one command; returns its unregister function. */
export function registerCommand(cmd: Command): () => void {
  useCommandStore.getState().register([cmd]);
  return () => useCommandStore.getState().unregister([cmd.id]);
}

/** Register several commands; returns a single unregister function. */
export function registerCommands(cmds: Command[]): () => void {
  useCommandStore.getState().register(cmds);
  const ids = cmds.map((c) => c.id);
  return () => useCommandStore.getState().unregister(ids);
}

/**
 * Effect helper: register on mount / deps change, unregister on cleanup.
 * Duplicate ids replace (last-write-wins) so hot reload and locale
 * re-registration are safe.
 */
export function useRegisterCommands(factory: () => Command[], deps: unknown[]): void {
  useEffect(() => {
    return registerCommands(factory());
    // The caller's deps array is the contract (mirrors useMemo semantics).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
