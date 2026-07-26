'use client';

/**
 * Headless dropdown menu: in-place absolute panel (no portal/popper),
 * role="menu" with arrow-key roving focus, Home/End, first-letter typeahead,
 * Esc/outside-click close, and flip-above when the viewport runs out.
 */

import {
  cloneElement,
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type HTMLAttributes,
  type ReactElement,
  type ReactNode,
} from 'react';
import { Check, type LucideIcon } from 'lucide-react';

import { formatChord } from '@/lib/shortcuts/keys';
import { cn } from '@/lib/utils';

interface DropdownContextValue {
  close: () => void;
}

const DropdownContext = createContext<DropdownContextValue | null>(null);

function useDropdownContext(): DropdownContextValue {
  const ctx = useContext(DropdownContext);
  if (!ctx) throw new Error('Dropdown.* must be used within <Dropdown>');
  return ctx;
}

export interface DropdownProps {
  /** A single focusable element (e.g. <Button>); aria/menu wiring is injected. */
  trigger: ReactElement<ButtonHTMLAttributes<HTMLButtonElement>>;
  align?: 'start' | 'end';
  children: ReactNode;
  className?: string;
  /** Extra classes for the menu panel (width etc.). */
  panelClassName?: string;
}

function menuItems(panel: HTMLElement): HTMLButtonElement[] {
  return Array.from(
    panel.querySelectorAll<HTMLButtonElement>(
      '[role="menuitem"]:not([aria-disabled="true"]), [role="menuitemradio"]:not([aria-disabled="true"])',
    ),
  );
}

export function Dropdown({ trigger, align = 'start', children, className, panelClassName }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const [flipUp, setFlipUp] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const close = useCallback(() => {
    setOpen(false);
    triggerRef.current?.focus();
  }, []);

  // Outside click closes without refocusing the trigger.
  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onPointerDown);
    return () => document.removeEventListener('mousedown', onPointerDown);
  }, [open]);

  // On open: flip above if the panel would overflow the viewport, then focus
  // the first item for keyboard users.
  useEffect(() => {
    if (!open) {
      setFlipUp(false);
      return;
    }
    const panel = panelRef.current;
    const wrapper = wrapperRef.current;
    if (panel && wrapper) {
      const rect = wrapper.getBoundingClientRect();
      setFlipUp(rect.bottom + panel.offsetHeight + 8 > window.innerHeight && rect.top > panel.offsetHeight);
      menuItems(panel)[0]?.focus();
    }
  }, [open]);

  const onPanelKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      const panel = panelRef.current;
      if (!panel) return;
      const items = menuItems(panel);
      const index = items.indexOf(document.activeElement as HTMLButtonElement);
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        items[(index + 1) % items.length]?.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        items[(index - 1 + items.length) % items.length]?.focus();
      } else if (e.key === 'Home') {
        e.preventDefault();
        items[0]?.focus();
      } else if (e.key === 'End') {
        e.preventDefault();
        items[items.length - 1]?.focus();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        e.stopPropagation();
        close();
      } else if (e.key === 'Tab') {
        setOpen(false);
      } else if (e.key.length === 1 && /\S/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
        // First-letter typeahead, starting after the focused item.
        const letter = e.key.toLowerCase();
        const rotated = [...items.slice(index + 1), ...items.slice(0, index + 1)];
        rotated.find((item) => item.textContent?.trim().toLowerCase().startsWith(letter))?.focus();
      }
    },
    [close],
  );

  return (
    <div ref={wrapperRef} className={cn('relative inline-block', className)}>
      {cloneElement(trigger, {
        // React 19: ref is a regular prop on host/forwardRef components.
        ref: (node: HTMLButtonElement | null) => {
          triggerRef.current = node;
        },
        'aria-haspopup': 'menu',
        'aria-expanded': open,
        onClick: (e: React.MouseEvent<HTMLButtonElement>) => {
          trigger.props.onClick?.(e);
          setOpen((v) => !v);
        },
      } as Partial<ButtonHTMLAttributes<HTMLButtonElement>>)}
      {open && (
        <div
          ref={panelRef}
          role="menu"
          onKeyDown={onPanelKeyDown}
          className={cn(
            'absolute z-50 min-w-44 rounded-md border border-border bg-overlay py-1 shadow-elev2',
            align === 'end' ? 'right-0' : 'left-0',
            flipUp ? 'bottom-full mb-1' : 'top-full mt-1',
            panelClassName,
          )}
        >
          <DropdownContext.Provider value={{ close }}>{children}</DropdownContext.Provider>
        </div>
      )}
    </div>
  );
}

export interface DropdownItemProps {
  children: ReactNode;
  onSelect?: () => void;
  icon?: LucideIcon;
  /** Chord spec (e.g. 'mod+k') rendered as a trailing hint. */
  shortcut?: string;
  destructive?: boolean;
  disabled?: boolean;
  className?: string;
}

export function DropdownItem({
  children,
  onSelect,
  icon: Icon,
  shortcut,
  destructive = false,
  disabled = false,
  className,
}: DropdownItemProps) {
  const { close } = useDropdownContext();
  return (
    <button
      type="button"
      role="menuitem"
      tabIndex={-1}
      aria-disabled={disabled || undefined}
      disabled={disabled}
      onClick={() => {
        close();
        onSelect?.();
      }}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm outline-none',
        'focus:bg-surface-2 hover:bg-surface-2 disabled:opacity-50',
        destructive ? 'text-danger' : 'text-text',
        className,
      )}
    >
      {Icon && <Icon className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />}
      <span className="flex-1 truncate">{children}</span>
      {shortcut && <span className="text-xs text-faint">{formatChord(shortcut)}</span>}
    </button>
  );
}

export interface DropdownRadioItemProps {
  children: ReactNode;
  checked: boolean;
  onSelect?: () => void;
  icon?: LucideIcon;
  className?: string;
}

export function DropdownRadioItem({ children, checked, onSelect, icon: Icon, className }: DropdownRadioItemProps) {
  const { close } = useDropdownContext();
  return (
    <button
      type="button"
      role="menuitemradio"
      aria-checked={checked}
      tabIndex={-1}
      onClick={() => {
        close();
        onSelect?.();
      }}
      className={cn(
        'flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-text outline-none',
        'focus:bg-surface-2 hover:bg-surface-2',
        className,
      )}
    >
      {Icon && <Icon className="h-4 w-4 shrink-0 text-muted" aria-hidden="true" />}
      <span className="flex-1 truncate">{children}</span>
      <Check className={cn('h-4 w-4', checked ? 'opacity-100' : 'opacity-0')} aria-hidden="true" />
    </button>
  );
}

export function DropdownLabel({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('px-3 py-1.5 text-xs font-medium text-muted', className)} {...props} />;
}

export function DropdownSeparator({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div role="separator" className={cn('my-1 h-px bg-border', className)} {...props} />;
}
