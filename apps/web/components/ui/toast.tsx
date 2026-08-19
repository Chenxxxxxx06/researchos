'use client';

/**
 * Global toast system. The queue lives in a module-level zustand store so the
 * imperative `toast(opts)` API works outside React (mutation callbacks etc.).
 * Mount <Toaster/> once (app/providers.tsx).
 */

import { useEffect, useRef } from 'react';
import { AlertTriangle, CheckCircle2, Info, X, XCircle, type LucideIcon } from 'lucide-react';
import { create } from 'zustand';

import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

export type ToastVariant = 'default' | 'success' | 'error' | 'warning';

export interface ToastOptions {
  title: string;
  description?: string;
  variant?: ToastVariant;
  /** Auto-dismiss delay in ms (default 5000). */
  duration?: number;
  action?: { label: string; onClick: () => void };
}

export interface ToastItem extends Required<Pick<ToastOptions, 'title' | 'variant' | 'duration'>> {
  id: number;
  description?: string;
  action?: { label: string; onClick: () => void };
}

interface ToastStore {
  toasts: ToastItem[];
  add: (item: ToastItem) => void;
  dismiss: (id: number) => void;
}

const MAX_TOASTS = 4;
let nextId = 1;

const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  add: (item) =>
    set((s) => ({ toasts: [...s.toasts, item].slice(-MAX_TOASTS) })),
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

/** Imperative API — safe to call from anywhere on the client. */
export function toast(opts: ToastOptions): number {
  const id = nextId++;
  useToastStore.getState().add({
    id,
    title: opts.title,
    description: opts.description,
    variant: opts.variant ?? 'default',
    duration: opts.duration ?? 5000,
    action: opts.action,
  });
  return id;
}

export function dismissToast(id: number): void {
  useToastStore.getState().dismiss(id);
}

const ICONS: Record<ToastVariant, LucideIcon> = {
  default: Info,
  success: CheckCircle2,
  error: XCircle,
  warning: AlertTriangle,
};

const VARIANT_CLASSES: Record<ToastVariant, { border: string; icon: string }> = {
  default: { border: 'border-l-info', icon: 'text-info' },
  success: { border: 'border-l-success', icon: 'text-success' },
  error: { border: 'border-l-danger', icon: 'text-danger' },
  warning: { border: 'border-l-warn', icon: 'text-warn' },
};

function ToastCard({ item }: { item: ToastItem }) {
  const { t } = useI18n();
  const dismiss = useToastStore((s) => s.dismiss);
  const remaining = useRef(item.duration);
  const startedAt = useRef(0);
  const timer = useRef<number | null>(null);

  // Timers pause on hover: track remaining time across pauses.
  useEffect(() => {
    const start = () => {
      startedAt.current = Date.now();
      timer.current = window.setTimeout(() => dismiss(item.id), remaining.current);
    };
    start();
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, [dismiss, item.id]);

  const pause = () => {
    if (timer.current !== null) {
      window.clearTimeout(timer.current);
      timer.current = null;
      remaining.current = Math.max(500, remaining.current - (Date.now() - startedAt.current));
    }
  };
  const resume = () => {
    if (timer.current === null) {
      startedAt.current = Date.now();
      timer.current = window.setTimeout(() => dismiss(item.id), remaining.current);
    }
  };

  const Icon = ICONS[item.variant];
  const classes = VARIANT_CLASSES[item.variant];

  return (
    <div
      role={item.variant === 'error' ? 'alert' : 'status'}
      onMouseEnter={pause}
      onMouseLeave={resume}
      className={cn(
        'ui-panel-enter pointer-events-auto flex w-80 items-start gap-2.5 rounded-md border border-border border-l-2',
        'bg-overlay p-3 shadow-elev2',
        classes.border,
      )}
    >
      <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', classes.icon)} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-text">{item.title}</p>
        {item.description && <p className="mt-0.5 text-xs text-muted">{item.description}</p>}
        {item.action && (
          <button
            type="button"
            className="mt-1.5 text-xs font-medium text-info hover:underline"
            onClick={() => {
              item.action?.onClick();
              dismiss(item.id);
            }}
          >
            {item.action.label}
          </button>
        )}
      </div>
      <button
        type="button"
        aria-label={t('toast.dismiss')}
        onClick={() => dismiss(item.id)}
        className="rounded p-0.5 text-faint hover:bg-surface-2 hover:text-text"
      >
        <X className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </div>
  );
}

declare global {
  interface Window {
    /** Dev/e2e-only hook (never installed in production builds). */
    __rosToast?: (opts: ToastOptions) => number;
  }
}

/** Fixed bottom-right viewport; mount exactly once. */
export function Toaster() {
  const toasts = useToastStore((s) => s.toasts);

  useEffect(() => {
    if (process.env.NODE_ENV !== 'production') {
      window.__rosToast = toast;
      return () => {
        delete window.__rosToast;
      };
    }
    return undefined;
  }, []);

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-4 right-4 z-[60] flex flex-col gap-2"
    >
      {toasts.map((item) => (
        <ToastCard key={item.id} item={item} />
      ))}
    </div>
  );
}
