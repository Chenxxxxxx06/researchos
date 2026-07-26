'use client';

/**
 * Modal dialog built on the native <dialog> element — no focus-trap library.
 * Focus trapping, Esc handling, and focus restoration are native; Esc is
 * intercepted (`cancel` event) so React state stays the source of truth.
 *
 * Never hand-roll a modal — see docs/DESIGN_TOKENS.md §4.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useId,
  useRef,
  type HTMLAttributes,
  type ReactNode,
} from 'react';
import { X } from 'lucide-react';

import { useI18n } from '@/lib/i18n';
import { cn } from '@/lib/utils';

interface DialogContextValue {
  labelId: string;
  descriptionId: string;
  onOpenChange: (open: boolean) => void;
}

const DialogContext = createContext<DialogContextValue | null>(null);

function useDialogContext(): DialogContextValue {
  const ctx = useContext(DialogContext);
  if (!ctx) throw new Error('Dialog.* must be used within <Dialog>');
  return ctx;
}

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: ReactNode;
  /** Extra classes on the <dialog> element (e.g. palette top placement). */
  className?: string;
}

export function Dialog({ open, onOpenChange, children, className }: DialogProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const labelId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) {
      el.showModal();
      // React's autoFocus runs before showModal (dialog still display:none),
      // so it cannot land. Elements marked data-autofocus get focused here.
      el.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    } else if (!open && el.open) {
      el.close();
    }
  }, [open]);

  // Native Esc → cancel event. preventDefault keeps the element open so the
  // React `open` prop remains authoritative; we close through state instead.
  const onCancel = useCallback(
    (e: React.SyntheticEvent) => {
      e.preventDefault();
      onOpenChange(false);
    },
    [onOpenChange],
  );

  // Backdrop click: clicks on ::backdrop dispatch to the <dialog> element
  // itself; content clicks target descendants. The dialog element is styled
  // transparent/padding-0 in globals.css so this check is exact.
  const onClick = useCallback(
    (e: React.MouseEvent<HTMLDialogElement>) => {
      if (e.target === e.currentTarget) onOpenChange(false);
    },
    [onOpenChange],
  );

  return (
    <dialog
      ref={ref}
      onCancel={onCancel}
      onClick={onClick}
      aria-labelledby={labelId}
      aria-describedby={descriptionId}
      className={cn('outline-none', className)}
    >
      <DialogContext.Provider value={{ labelId, descriptionId, onOpenChange }}>
        {open ? children : null}
      </DialogContext.Provider>
    </dialog>
  );
}

const SIZES = { sm: 'max-w-sm', md: 'max-w-lg', lg: 'max-w-2xl' } as const;

export interface DialogContentProps extends HTMLAttributes<HTMLDivElement> {
  size?: keyof typeof SIZES;
}

export function DialogContent({ size = 'md', className, ...props }: DialogContentProps) {
  return (
    <div
      className={cn(
        'w-[calc(100vw-2rem)] rounded-lg border border-border bg-overlay text-text shadow-elev3',
        SIZES[size],
        className,
      )}
      {...props}
    />
  );
}

export function DialogHeader({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex items-start justify-between gap-4 p-4 pb-2', className)} {...props} />;
}

export function DialogTitle({ className, ...props }: HTMLAttributes<HTMLHeadingElement>) {
  const { labelId } = useDialogContext();
  return <h2 id={labelId} className={cn('text-base font-semibold text-text', className)} {...props} />;
}

export function DialogDescription({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  const { descriptionId } = useDialogContext();
  return <p id={descriptionId} className={cn('mt-1 text-sm text-muted', className)} {...props} />;
}

export function DialogFooter({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('flex justify-end gap-2 p-4 pt-2', className)} {...props} />;
}

/** Icon close button, usually placed inside DialogHeader. */
export function DialogClose({ className }: { className?: string }) {
  const { onOpenChange } = useDialogContext();
  const { t } = useI18n();
  return (
    <button
      type="button"
      aria-label={t('common.close')}
      onClick={() => onOpenChange(false)}
      className={cn(
        'rounded-md p-1 text-muted hover:bg-surface-2 hover:text-text',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60',
        className,
      )}
    >
      <X className="h-4 w-4" aria-hidden="true" />
    </button>
  );
}
