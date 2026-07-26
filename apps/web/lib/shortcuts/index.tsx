'use client';

/**
 * Global shortcut layer: ONE window keydown listener that dispatches to
 * commands registered in lib/command/registry with a `shortcut`.
 *
 * - Chords with `mod` (mod+k, mod+s, mod+enter) fire even in editable targets
 *   (preventDefault suppresses e.g. the browser save dialog).
 * - Bare-key chords (`?`) are ignored while typing.
 * - `g <letter>` sequences: bare `g` outside editable targets arms a 1200ms
 *   pending state (with a subtle hint chip); the next key is matched.
 * - Collisions: last registration wins (registry iteration order guarantees).
 */

import { useQueryClient } from '@tanstack/react-query';
import { useParams, useRouter } from 'next/navigation';
import { useEffect, useRef, useState, type ReactNode } from 'react';

import {
  isEditableTarget,
  isSequence,
  matchesChord,
  parseChord,
} from '@/lib/shortcuts/keys';
import { useCommandStore, type Command, type CommandContext } from '@/lib/command/registry';

const SEQUENCE_TIMEOUT_MS = 1200;

export function ShortcutProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const params = useParams<{ projectId?: string }>();
  const queryClient = useQueryClient();
  const [pendingKey, setPendingKey] = useState<string | null>(null);

  // Latest context in a ref so the single listener never needs re-binding.
  const ctxRef = useRef<CommandContext | null>(null);
  ctxRef.current = {
    router: { push: (href: string) => router.push(href) },
    projectId: params?.projectId ?? null,
    queryClient,
    close: () => useCommandStore.getState().setOpen(false),
  };

  const pendingRef = useRef<{ key: string; timer: number } | null>(null);

  useEffect(() => {
    const clearPending = () => {
      if (pendingRef.current) {
        window.clearTimeout(pendingRef.current.timer);
        pendingRef.current = null;
        setPendingKey(null);
      }
    };

    const runCommand = (cmd: Command, e: KeyboardEvent) => {
      const ctx = ctxRef.current;
      if (!ctx) return false;
      if (cmd.enabled && !cmd.enabled(ctx)) return false;
      e.preventDefault();
      void cmd.run(ctx);
      return true;
    };

    const onKeyDown = (e: KeyboardEvent) => {
      // Modifier keydowns themselves are never bindings.
      if (e.key === 'Control' || e.key === 'Meta' || e.key === 'Alt' || e.key === 'Shift') {
        return;
      }
      const commands = Array.from(useCommandStore.getState().commands.values());
      const editable = isEditableTarget(e.target);

      // 1) Armed sequence: try `<pending> <key>` (last registration wins).
      if (pendingRef.current) {
        const spec = `${pendingRef.current.key} ${e.key.toLowerCase()}`;
        clearPending();
        if (!editable) {
          for (let i = commands.length - 1; i >= 0; i--) {
            const cmd = commands[i]!;
            if (cmd.shortcut && isSequence(cmd.shortcut) && cmd.shortcut === spec) {
              if (runCommand(cmd, e)) return;
            }
          }
        }
        return; // any non-match just disarms
      }

      // 2) Chords.
      const hasModifier = e.ctrlKey || e.metaKey;
      for (let i = commands.length - 1; i >= 0; i--) {
        const cmd = commands[i]!;
        if (!cmd.shortcut || isSequence(cmd.shortcut)) continue;
        const chord = parseChord(cmd.shortcut);
        if (!matchesChord(e, chord)) continue;
        // Bare-key chords are ignored while typing; mod-chords always fire.
        if (editable && !(chord.ctrl || chord.meta)) continue;
        if (runCommand(cmd, e)) return;
      }

      // 3) Sequence starter: bare `g` outside editable targets.
      if (!editable && !hasModifier && !e.altKey && e.key.toLowerCase() === 'g') {
        const timer = window.setTimeout(() => {
          pendingRef.current = null;
          setPendingKey(null);
        }, SEQUENCE_TIMEOUT_MS);
        pendingRef.current = { key: 'g', timer };
        setPendingKey('g');
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => {
      window.removeEventListener('keydown', onKeyDown);
      clearPending();
    };
  }, []);

  return (
    <>
      {children}
      {pendingKey && (
        <div
          aria-hidden="true"
          className="pointer-events-none fixed bottom-4 left-4 z-[60] rounded-md border border-border bg-overlay px-2 py-1 text-xs text-muted shadow-elev1"
        >
          {pendingKey} …
        </div>
      )}
    </>
  );
}
