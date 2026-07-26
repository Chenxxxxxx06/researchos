# ResearchOS Design Tokens & Primitives

Reference for every frontend partition. The design-system partition owns
`apps/web/{app,components,features/workspace,lib/{theme,shortcuts,command,i18n}}`;
feature partitions restyle their own files using this document.

## 1. Semantic color tokens

Defined in `apps/web/app/globals.css` as space-separated RGB triplets
(`--color-*`), mapped in `tailwind.config.ts` via
`rgb(var(--…) / <alpha-value>)` so alpha utilities (`bg-surface/95`) work.
Theme switching stamps `data-theme="light|dark"` on `<html>`.

| Token | Tailwind class | Light | Dark | Usage rule |
|---|---|---|---|---|
| `--color-bg` | `bg-bg` | `250 250 250` | `12 12 14` | App canvas (main content area) |
| `--color-surface` | `bg-surface` | `255 255 255` | `24 24 27` | Cards, panels, TopBar, sidebars |
| `--color-surface-2` | `bg-surface-2` | `245 245 245` | `39 39 42` | Nested/hover surfaces, code blocks |
| `--color-overlay` | `bg-overlay` | `255 255 255` | `31 31 35` | Dialogs, dropdowns, palette |
| `--color-border` | `border-border` | `229 229 229` | `46 46 51` | Hairlines, dividers |
| `--color-border-strong` | `border-border-strong` | `212 212 212` | `63 63 70` | Inputs, emphasized borders |
| `--color-text` | `text-text` | `23 23 23` | `244 244 245` | Primary text |
| `--color-text-muted` | `text-muted` | `115 115 115` | `161 161 170` | Secondary text |
| `--color-text-faint` | `text-faint` | `163 163 163` | `113 113 122` | Placeholders, disabled |
| `--color-accent` | `bg-accent` / `text-accent` | `15 23 42` | `226 232 240` | Primary actions, active nav |
| `--color-accent-fg` | `text-accent-fg` | `255 255 255` | `15 23 42` | Text on accent |
| `--color-accent-hover` | `bg-accent-hover` | `30 41 59` | `203 213 225` | Accent hover |
| `--color-focus` | `ring-focus` | `59 130 246` | `96 165 250` | Focus rings |
| `--color-success(-bg)` | `text-success` / `bg-success-bg` | `22 163 74` / `240 253 244` | `74 222 128` / `20 45 31` | Positive status |
| `--color-warn(-bg)` | `text-warn` / `bg-warn-bg` | `217 119 6` / `255 251 235` | `251 191 36` / `54 42 17` | Warnings, dirty dots |
| `--color-danger(-bg)` | `text-danger` / `bg-danger-bg` | `220 38 38` / `254 242 242` | `248 113 113` / `55 24 24` | Destructive, errors |
| `--color-info(-bg)` | `text-info` / `bg-info-bg` | `37 99 235` / `239 246 255` | `96 165 250` / `23 37 60` | Info pills |

Typical recipes: `bg-surface border border-border text-text`,
`text-muted`, `bg-accent text-accent-fg hover:bg-accent-hover`,
`shadow-elev2 rounded-lg`.

## 2. Elevation & radii

| Token | Tailwind | Use |
|---|---|---|
| `--shadow-1` | `shadow-elev1` | Subtle card lift |
| `--shadow-2` | `shadow-elev2` | Dropdowns, popovers, toasts |
| `--shadow-3` | `shadow-elev3` | Dialogs, command palette |
| `--radius-sm` (6px) | `rounded-sm` | Chips, kbd |
| `--radius-md` (8px) | `rounded-md` | Buttons, inputs, menu panels |
| `--radius-lg` (12px) | `rounded-lg` | Cards, dialogs |

Dark shadows add a 1px inset border-color ring for edge definition.

## 3. Migration mapping (feature specs apply this to their own files)

| Old (raw palette) | New (token) |
|---|---|
| `bg-white` | `bg-surface` |
| `bg-neutral-50` | `bg-bg` (canvas) or `bg-surface-2` (nested) |
| `bg-neutral-100` | `bg-surface-2` |
| `border-neutral-100/200` | `border-border` |
| `border-neutral-300` | `border-border-strong` |
| `text-neutral-900` | `text-text` |
| `text-neutral-600/500` | `text-muted` |
| `text-neutral-400/300` | `text-faint` |
| `bg-neutral-900 text-white` (primary buttons/nav) | `bg-accent text-accent-fg` |
| `text-red-600` / `bg-red-*` pills | `text-danger` / `<Badge variant="danger">` |
| amber/yellow status pills | `<Badge variant="warn">` |
| emerald/green status pills | `<Badge variant="success">` |
| blue info pills | `<Badge variant="info">` |
| `shadow-sm/md` on overlays | `shadow-elev1/2/3` |
| `focus-visible:ring-neutral-400` | `focus-visible:ring-focus/60` |

**Transitional compat ramp**: `white` and the whole `neutral` scale are
currently remapped in `tailwind.config.ts` to `--gray-*` variables that invert
in dark mode, so unmigrated files stay presentable. This layer is
**transitional**. Removal criterion: when
`grep -R "neutral-" apps/web --include='*.tsx'` returns nothing, delete the
`white`/`neutral` overrides in `tailwind.config.ts` and the `--gray-*` blocks
in `globals.css`.

## 4. Primitive catalog (`@/components/ui/*`)

All primitives are token-only, `cn()`-merged, focus-ring wired. Labels come
from callers via `t()` — primitives are i18n-free except tiny defaults.

| Component | Props (essentials) | Notes / do-don't |
|---|---|---|
| `Button` | `variant: primary\|secondary\|ghost\|outline\|destructive`, `size: sm\|md\|lg\|icon`, `loading` | `loading` renders a spinner + `aria-busy` and disables. Don't hand-style `<button>`s. |
| `Input` / `Textarea` | native props | `aria-invalid` turns the border `danger`. |
| `Dialog` | `open`, `onOpenChange`, + `DialogContent(size sm\|md\|lg)/Header/Title/Description/Footer/Close` | Native `<dialog>` (focus trap, Esc, focus restore are native). **Never hand-roll a modal.** Backdrop click + Esc close via `onOpenChange(false)`. |
| `Dropdown` | `trigger` (single focusable element), `align: start\|end`, children: `DropdownItem(icon, shortcut, destructive, onSelect)`, `DropdownRadioItem(checked)`, `DropdownLabel`, `DropdownSeparator` | `role="menu"`, arrow-key roving focus, typeahead, flip-above. Don't use native `<select>` for command-like menus. |
| `Tabs` | `value`, `onValueChange` + `TabsList/TabsTrigger/TabsContent` | Underline style; ARIA tablist with arrow-key nav. |
| `Tooltip` | `content`, `side: top\|bottom\|right`, `shortcut?` | 350ms hover delay, immediate on focus. For icon-only buttons, still set `aria-label`. |
| `toast()` / `<Toaster/>` | see §6 | Toaster is mounted once in `app/providers.tsx` — never mount again. |
| `Badge` | `variant: neutral\|success\|warn\|danger\|info\|accent\|outline`, `size: sm\|md`, `dot` | Replaces ad-hoc status pill span recipes. |
| `Skeleton` / `Skeleton.Text` | `lines` | `bg-surface-2` pulse. |
| `EmptyState` | `icon` (Lucide), `title`, `body?`, `actions?` | Dashed border container; supply feature CTAs via `actions`. |
| `Kbd` | `keys` ('mod+k' or 'g i'), `raw?` | Platform-aware: ⌘K on macOS, Ctrl K elsewhere. |
| `DiffText` | `before`, `after`, `mode: words\|chars` | Inline LCS diff rendered with native `<del>`/`<ins>`; falls back wholesale past a 250k-cell budget. |

## 5. Command palette — registering commands

The registry (`@/lib/command/registry`) is the single source of truth for the
palette (mod+k), the global shortcut layer, and the `?` cheatsheet.

```tsx
'use client';
import { useRegisterCommands } from '@/lib/command/registry';
import { Save } from 'lucide-react';
import { useI18n } from '@/lib/i18n';

function IdeCommands({ save }: { save: () => void }) {
  const { t } = useI18n();
  useRegisterCommands(
    () => [
      {
        id: 'ide.save-active',          // unique; re-register replaces
        title: t('ide.saveActive'),     // pre-localized; re-registers on [t]
        section: 'file',                // navigate|action|theme|file|paper|run
        icon: Save,
        shortcut: 'mod+s',              // chord — or a sequence like 'g x'
        enabled: (ctx) => Boolean(ctx.projectId), // hidden when false
        run: () => save(),
      },
    ],
    [t, save],
  );
  return null;
}
```

Rules:
- `run(ctx)` receives `{ router, projectId, queryClient, close }`.
- Duplicate ids replace (last-write-wins) — safe under hot reload/locale change.
- Shortcut collisions: the **last registration wins**.
- `mod+*` chords fire even in inputs/Monaco (with `preventDefault`); bare keys
  (`?`) and `g` sequences are ignored while typing.
- Sequences are `g` + letter; built-ins already use
  `g j/o/r/i/e/p/k/b/s` — pick unclaimed letters.

## 6. Toasts

```ts
import { toast } from '@/components/ui/toast';

toast({ title: t('paper.saved') });
toast({
  title: t('common.error'),
  description: err.message,
  variant: 'error',              // default | success | error | warning
  action: { label: t('common.retry'), onClick: retry },
});
```

Imperative — callable from mutation callbacks. Max 4 stacked; auto-dismiss
5s (pauses on hover); `error` renders `role="alert"`.

## 7. Monaco & charts theming

```tsx
// Editors — one-line import swap, theming handled internally:
import { MonacoEditor, MonacoDiff } from '@/components/editor/monaco';
// (replaces '@/lib/ide/monaco'; passing your own `theme` prop still wins)

// Recharts:
import { useChartTheme } from '@/lib/theme/charts';
const { colors, grid, axis, tooltip } = useChartTheme();
// colors: 6 categorical series hexes; grid/axis: stroke hexes;
// tooltip: { background, border, color } for contentStyle.
```

Raw theme state when needed: `useTheme()` from `@/lib/theme` →
`{ preference: 'light'|'dark'|'system', resolved: 'light'|'dark', setTheme }`.

## 8. Compat ramp status

Transitional (see §3). Do **not** write new `neutral-*` / `bg-white` /
`text-white` classes — CI-facing acceptance greps owned directories for zero
matches, and every new occurrence delays ramp removal.

## 9. Accessibility checklist (baked into primitives)

- Focus: every interactive element shows the `--color-focus` ring
  (`focus-visible`, 2px, offset 2).
- Dialog: native `<dialog>` semantics; `aria-labelledby`/`aria-describedby`
  auto-wired; Esc + backdrop click close; focus restored on close.
- Dropdown: `aria-haspopup="menu"` + `aria-expanded` trigger; `role="menu"`
  panel; roving `tabIndex={-1}` items; Esc/outside-click/Tab close.
- Palette: `role="combobox"` input with `aria-activedescendant` into a
  `role="listbox"`.
- Toasts: polite `aria-live` region; errors use `role="alert"`.
- Icon-only buttons: always pass `aria-label` (Tooltip is not a substitute).
- Diff runs render native `<del>`/`<ins>` so screen readers announce edits.
- Reduced motion: global `prefers-reduced-motion` kill-switch in globals.css.
