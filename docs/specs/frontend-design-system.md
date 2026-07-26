# Spec: frontend-design-system

Workstream: design system + IDE cockpit polish (owner wishlist 4; realizes INNOVATION_IDEAS WS7-1 and WS7-2, plus the shell/primitives substrate that WS7-3/WS7-4 and every other frontend spec builds on).

Implementation partition (owned files): `apps/web/app/**` (layouts, pages, globals.css), `apps/web/tailwind.config.ts`, `apps/web/components/**`, `apps/web/features/workspace/**`, `apps/web/lib/theme/**` (new), `apps/web/lib/shortcuts/**` (new), `apps/web/lib/command/**` (new), `apps/web/lib/i18n/**`, `apps/web/docs deliverable docs/DESIGN_TOKENS.md`, plus new Playwright specs under `apps/web/e2e/`.

---

## Objective (user-visible outcome, tied to owner wishlist)

The owner's wishlist 4 asks for a "prettier IDE" / professional research cockpit. After this spec:

1. The entire app renders from a **semantic token system** (light + dark), with a FOUC-free theme toggle (light/dark/system) in the TopBar and Settings that also themes Monaco editors and Recharts charts. Dark mode works *immediately* across the whole app (including feature areas not yet migrated) via a transitional palette-inversion compatibility layer.
2. A **component primitive kit** (Button, Input, Textarea, Dialog, Dropdown, Tabs, Tooltip, Toast, Skeleton, EmptyState, Badge, Kbd, DiffText, themed Monaco wrapper) exists in `components/ui` — accessible, zero heavy deps — so every feature spec restyles consistently instead of hand-rolling.
3. **Ctrl/Cmd+K command palette** with fuzzy search over navigation + actions, an extensible `registerCommand` zustand registry other specs push into, and a **global shortcut layer** (`g i` → IDE, `mod+k`, `?` cheatsheet).
4. A refined **workspace shell**: TopBar with theme toggle, user menu, command-palette hint; SideRail with lucide icons and proper active states; polished org switcher + new project switcher; a global toast system.
5. Everything new is **bilingual (zh-CN / en-US)**, and `docs/DESIGN_TOKENS.md` documents the tokens, primitives, and migration mapping for all other implementers.

---

## Current state (concrete, file:line)

- **Dead tokens, dark mode actively disabled.** `apps/web/app/globals.css:5-13` declares `--color-bg/surface/border/text/text-muted/accent` that no component consumes; lines 15-17 force `color-scheme: light` even under `prefers-color-scheme: dark`; line 20 styles `body` with raw `bg-neutral-50 text-neutral-900`. `apps/web/tailwind.config.ts:10-12` has an empty `theme.extend` — no semantic colors, no `darkMode` config.
- **Raw palette everywhere.** All shell files hardcode `neutral-*`: `features/workspace/TopBar.tsx:24-31` (`border-neutral-200 bg-white/95`, `text-neutral-900`), `features/workspace/SideRail.tsx:29-49` (`bg-white/80`, active = `bg-neutral-900 text-white`, emoji icons 🏠🔍⌨️ at lines 12-19), `components/ui/button.tsx:8-13` (all four variants raw), `card.tsx:8`, `input.tsx:10-12`, `label.tsx:8`, `skeleton.tsx:6`, `app/(auth)/layout.tsx:11-21`, `app/(workspace)/layout.tsx:41` (`bg-neutral-50`), `app/(workspace)/projects/[projectId]/ide/page.tsx:23-45`, `settings/page.tsx` throughout.
- **UI kit = 5 primitives.** `components/ui/` contains only button, card, input, label, skeleton (ARCHITECTURE_MAP §3.8). No dialog/dropdown/tabs/tooltip/toast/badge/empty-state anywhere; `features/projects/CreateProjectDialog.tsx` hand-rolls a modal (a11y gaps noted in ARCHITECTURE_MAP §4.17).
- **No keyboard layer.** Zero hits for `metaKey/ctrlKey/keydown` across `apps/web` (INNOVATION_IDEAS WS7-2); every action is mouse-only. No command palette.
- **Monaco/Recharts light-only.** `lib/ide/monaco.tsx:7-12` exports untemed dynamic wrappers; usage sites pass no `theme` prop (`features/ide/EditorPane.tsx:77`, `features/paper/PaperWorkspace.tsx:52`, `features/ide/PatchDiff.tsx:26`). `features/experiments/MetricsChart.tsx:21` hardcodes `COLORS = ['#2563eb', …]` and grid/axis hex at lines 55-57.
- **i18n gaps.** `lib/i18n/index.tsx:40` — `t()` has no interpolation; locale flashes zh-CN before the `localStorage` read at lines 29-32; `app/layout.tsx:14` hardcodes `<html lang="en">` while the default locale is zh-CN; `app/(auth)/register/page.tsx` has hardcoded English strings (ARCHITECTURE_MAP §3.8). Dictionary parity is compile-enforced: `en-US.ts:3` is typed `Record<DictKey, string>` with `DictKey = keyof typeof zhCN` (`zh-CN.ts:132`).
- **Shell rough edges.** `OrgSwitcher.tsx:22-33` and `LanguageSwitcher.tsx:8-16` are bare native `<select>`s; TopBar has no theme toggle, no user menu (sign-out is a raw button at `TopBar.tsx:32-34`); no project switcher — switching projects requires navigating back to `/projects`. No `error.tsx` / `not-found.tsx` anywhere under `app/` (ARCHITECTURE_MAP §3.8).
- **No preferences persistence surface.** Theme/locale live only in `localStorage` (`ros_locale`, `lib/i18n/index.tsx:15`); there is no preferences API (backend owned by the experiments-figures spec — see Cross-partition requests).

### Superseded / adjusted prior decisions

- The implicit "light-only" styling stance (`globals.css:15-17`, shipped in the "beautify all pages" phase, commit 94b7a8e) is **superseded**: dark mode becomes first-class. Rationale: owner wishlist 4 + WS7-1 (priority 20).
- P1-D12 mentions "shadcn-style primitives and Radix peers". **We explicitly do not adopt Radix**: primitives are built on native `<dialog>` + headless patterns with zero new runtime deps (except `lucide-react`). Rationale: hard constraint "zero heavy deps", smaller bundle, no version churn.
- P3-D13 (Monaco via CDN loader) is **unchanged** — theming uses `defineTheme` through the same loader; no bundling change.
- Phase 0 "TanStack Query + Zustand" split is honored: the command registry and toast queue are ephemeral UI state in zustand; no server state moves.

---

## Design (algorithms & data flow)

### D1. Semantic token system (two layers)

**Layer 1 — semantic tokens (the real API).** CSS custom properties as space-separated RGB triplets (Tailwind `<alpha-value>`-compatible), defined in `globals.css`:

| Token | Light | Dark | Purpose |
|---|---|---|---|
| `--color-bg` | `250 250 250` | `12 12 14` | app canvas |
| `--color-surface` | `255 255 255` | `24 24 27` | cards, panels, TopBar |
| `--color-surface-2` | `245 245 245` | `39 39 42` | nested/hover surfaces, code blocks |
| `--color-overlay` | `255 255 255` | `31 31 35` | dialogs, dropdowns, palette |
| `--color-border` | `229 229 229` | `46 46 51` | hairlines |
| `--color-border-strong` | `212 212 212` | `63 63 70` | inputs, emphasized borders |
| `--color-text` | `23 23 23` | `244 244 245` | primary text |
| `--color-text-muted` | `115 115 115` | `161 161 170` | secondary text |
| `--color-text-faint` | `163 163 163` | `113 113 122` | placeholders, disabled |
| `--color-accent` | `15 23 42` | `226 232 240` | primary actions, active nav |
| `--color-accent-fg` | `255 255 255` | `15 23 42` | text on accent |
| `--color-accent-hover` | `30 41 59` | `203 213 225` | accent hover |
| `--color-focus` | `59 130 246` | `96 165 250` | focus rings |
| `--color-success` / `--color-success-bg` | `22 163 74` / `240 253 244` | `74 222 128` / `20 45 31` | positive status |
| `--color-warn` / `--color-warn-bg` | `217 119 6` / `255 251 235` | `251 191 36` / `54 42 17` | warnings, dirty dots |
| `--color-danger` / `--color-danger-bg` | `220 38 38` / `254 242 242` | `248 113 113` / `55 24 24` | destructive, errors |
| `--color-info` / `--color-info-bg` | `37 99 235` / `239 246 255` | `96 165 250` / `23 37 60` | info pills |

Elevation (non-color, so plain values): `--shadow-1` (subtle card), `--shadow-2` (dropdown/popover), `--shadow-3` (dialog/palette) — dark variants use higher-alpha black + a 1px inset border-color ring. Radii: `--radius-sm: 6px`, `--radius-md: 8px`, `--radius-lg: 12px`.

`tailwind.config.ts` maps them (excerpt of the exact shape):

```ts
theme: {
  extend: {
    colors: {
      bg: 'rgb(var(--color-bg) / <alpha-value>)',
      surface: 'rgb(var(--color-surface) / <alpha-value>)',
      'surface-2': 'rgb(var(--color-surface-2) / <alpha-value>)',
      overlay: 'rgb(var(--color-overlay) / <alpha-value>)',
      border: 'rgb(var(--color-border) / <alpha-value>)',
      'border-strong': 'rgb(var(--color-border-strong) / <alpha-value>)',
      text: 'rgb(var(--color-text) / <alpha-value>)',
      muted: 'rgb(var(--color-text-muted) / <alpha-value>)',
      faint: 'rgb(var(--color-text-faint) / <alpha-value>)',
      accent: 'rgb(var(--color-accent) / <alpha-value>)',
      'accent-fg': 'rgb(var(--color-accent-fg) / <alpha-value>)',
      'accent-hover': 'rgb(var(--color-accent-hover) / <alpha-value>)',
      focus: 'rgb(var(--color-focus) / <alpha-value>)',
      success: { DEFAULT: 'rgb(var(--color-success) / <alpha-value>)', bg: 'rgb(var(--color-success-bg) / <alpha-value>)' },
      warn:    { DEFAULT: 'rgb(var(--color-warn) / <alpha-value>)',    bg: 'rgb(var(--color-warn-bg) / <alpha-value>)' },
      danger:  { DEFAULT: 'rgb(var(--color-danger) / <alpha-value>)',  bg: 'rgb(var(--color-danger-bg) / <alpha-value>)' },
      info:    { DEFAULT: 'rgb(var(--color-info) / <alpha-value>)',    bg: 'rgb(var(--color-info-bg) / <alpha-value>)' },
    },
    borderRadius: { sm: 'var(--radius-sm)', md: 'var(--radius-md)', lg: 'var(--radius-lg)' },
    boxShadow: { elev1: 'var(--shadow-1)', elev2: 'var(--shadow-2)', elev3: 'var(--shadow-3)' },
  },
},
darkMode: ['selector', '[data-theme="dark"]'],
```

Usage classes read naturally: `bg-surface border-border text-text`, `text-muted`, `bg-accent text-accent-fg`, `shadow-elev2 rounded-lg`.

**Layer 2 — transitional compatibility ramp (so unmigrated features flip too).** ~55 feature files hardcode `neutral-*` / `bg-white`; their restyling belongs to their own specs. To avoid a half-broken dark mode this session, the Tailwind `neutral` ramp and `white` are **remapped to CSS variables that invert in dark**:

1. `globals.css` defines `--gray-0` (white) and `--gray-50…950` in `:root`; the `[data-theme="dark"]` block reassigns them with an inverted ladder (`--gray-0` → `24 24 27`, `--gray-50` → `18 18 20`, `--gray-100` → `39 39 42`, … `--gray-900` → `244 244 245`, `--gray-950` → `250 250 250`).
2. `tailwind.config.ts` overrides `colors.white = 'rgb(var(--gray-0) / <alpha-value>)'` and `colors.neutral.{50..950} = 'rgb(var(--gray-N) / <alpha-value>)'`.

Effect: `bg-white` cards become dark surfaces, `bg-neutral-900 text-white` primary buttons become light-on-dark automatically, `bg-white/95` alpha usage keeps working. Status hues (`amber-*`, `emerald-*`, `red-*`, `green-*` pills) stay stock Tailwind — legible on dark, migrated to `Badge` by feature specs. This layer is **documented as transitional** in DESIGN_TOKENS.md with a removal criterion: once `grep -R "neutral-" apps/web --include='*.tsx'` is clean, delete the ramp.

**Base styles rewrite** (`globals.css`): `body { @apply bg-bg text-text antialiased; }`; scrollbar colors from `--color-border/-strong`; focus ring `outline: 2px solid rgb(var(--color-focus) / .6)`; the `select` chevron SVG gets a dark variant (two data-URIs switched under `[data-theme="dark"]`); `@media (prefers-reduced-motion: reduce)` kills transitions; `kbd` element base style; native `<dialog>::backdrop { background: rgb(0 0 0 / .5); }`. The `color-scheme: light` force at lines 15-17 is deleted; `color-scheme` is set per theme block (`:root { color-scheme: light }`, `:root[data-theme="dark"] { color-scheme: dark }`).

### D2. Theme engine (FOUC-free, persisted)

Data model: `ThemePreference = 'light' | 'dark' | 'system'`, `ResolvedTheme = 'light' | 'dark'`. Storage key `ros-theme` (localStorage, stores the *preference*; absent = `system`).

1. **Inline boot script** in `app/layout.tsx` `<head>` (server component, `dangerouslySetInnerHTML`, ~10 lines, runs before first paint):
   reads `ros-theme`; resolves `system` via `matchMedia('(prefers-color-scheme: dark)')`; stamps `document.documentElement.dataset.theme = resolved`; also reads `ros_locale` and stamps `document.documentElement.lang` (fixes the hardcoded `lang="en"` at `app/layout.tsx:14`). Wrapped in `try/catch`; `<html suppressHydrationWarning>` added because the script mutates attributes pre-hydration.
2. **`ThemeProvider`** (`lib/theme/index.tsx`, mounted in `app/providers.tsx` inside `I18nProvider`): context `{ preference, resolved, setTheme(pref) }`.
   - Initial state read from `document.documentElement.dataset.theme` + localStorage (client-only; provider renders children immediately).
   - `setTheme`: writes localStorage, re-stamps `data-theme` (resolving `system`), updates context, and fire-and-forgets `PUT /users/me/preferences {"theme": pref}` (see Cross-partition; 404/network errors silently ignored — localStorage remains source of truth).
   - When `preference === 'system'`, subscribes to the `matchMedia` change event and re-stamps live.
   - **Server sync-down**: on first mount, if localStorage has *no* explicit `ros-theme` entry, `GET /users/me/preferences` (via `apiRequest`, errors ignored) and adopt `theme` if present. Device-local explicit choice always wins; the server carries the preference to fresh browsers.
3. **Monaco theming** (`lib/theme/monaco.ts`): exports `MONACO_LIGHT = 'ros-light'`, `MONACO_DARK = 'ros-dark'`, `defineMonacoThemes(monaco)` calling `monaco.editor.defineTheme` twice (`ros-light` inherits `'vs'`, `ros-dark` inherits `'vs-dark'`; both override `editor.background`/`editorGutter.background` to the hex of `--color-surface`, selection/lineHighlight tuned to `--color-surface-2`), and `monacoThemeFor(resolved): string`. The themed wrapper `components/editor/monaco.tsx` re-exports `MonacoEditor`/`MonacoDiff` built on the same `@monaco-editor/react` dynamic import pattern as `lib/ide/monaco.tsx:7-12`, wiring `beforeMount={defineMonacoThemes}` and `theme={monacoThemeFor(useTheme().resolved)}` so consumers get theming with a one-line import swap (see Cross-partition).
4. **Chart palette** (`lib/theme/charts.ts`): static hex maps per resolved theme (no `getComputedStyle` → SSR-safe, no reflow):
   `CHART_COLORS: { light: string[]; dark: string[] }` (6 categorical series colors each, dark set brightened for contrast), and `useChartTheme(): { colors: string[]; grid: string; axis: string; tooltip: { background, border, color } }` derived from `useTheme().resolved`. `MetricsChart` consumes it via cross-partition request.

### D3. Component primitives (`components/ui`, zero heavy deps)

All primitives: token-only styling, `forwardRef`, `cn()` merge, focus-visible rings via `--color-focus`, i18n-free (labels supplied by callers) except tiny defaults (e.g. Dialog close button `aria-label` from `t('common.close')`).

1. **Button** (modified): variants `primary | secondary | ghost | outline | destructive`, sizes `sm | md | lg | icon` (icon = square, for TopBar), new `loading?: boolean` prop rendering an inline SVG spinner + `aria-busy`, `disabled` while loading.
2. **Input** (modified) + **Textarea** (new, same styling): tokens (`border-border-strong bg-surface placeholder:text-faint`), `aria-invalid` styling (`border-danger`).
3. **Dialog** (new, native `<dialog>`): `<Dialog open onOpenChange>` + `DialogContent/Header/Title/Description/Footer/Close`.
   - `useEffect`: `open ? ref.showModal() : ref.close()`; native focus trap + `Esc` (`cancel` event → `preventDefault` + `onOpenChange(false)`); backdrop click closes when `e.target === dialogEl` and the click point is outside the content box; focus restoration is native.
   - `aria-labelledby`/`aria-describedby` auto-wired via generated ids (`useId`). Sizes `sm | md | lg` (max-w). Body scroll locked via `body:has(dialog[open]) { overflow: hidden }` in globals.css.
4. **Dropdown** (new, headless menu): `<Dropdown trigger={<Button/>} align='start'|'end'>` with `DropdownItem (icon?, shortcut?, destructive?, onSelect)`, `DropdownLabel`, `DropdownSeparator`, and `DropdownRadioItem` (checkmark) for switchers.
   - Trigger gets `aria-haspopup="menu"`/`aria-expanded`; panel `role="menu"` rendered in-place with `position: absolute` inside a `relative` wrapper (no portal, no popper): default below-start, flips above when `getBoundingClientRect().bottom + panelHeight > innerHeight`.
   - Keyboard: `ArrowUp/Down` roving focus (`tabIndex={-1}` items, `.focus()`), `Home/End`, `Enter/Space` selects, `Esc`/outside-click/`blur` closes, typeahead by first letter.
5. **Tabs** (new): `<Tabs value onValueChange>` + `TabsList (role="tablist")` / `TabsTrigger (role="tab", aria-selected, roving tabindex, arrow-key nav)` / `TabsContent (role="tabpanel")`. Underline style (active: `border-b-2 border-accent text-text`; inactive: `text-muted`).
6. **Tooltip** (new): `<Tooltip content side='top'|'bottom'|'right'>` wraps a single child; shows on `mouseenter` (350ms delay) and `focus-visible` (immediate); `role="tooltip"` + `aria-describedby`; absolute positioning, pointer-events-none, `shadow-elev2`. Accepts `shortcut?: string` rendered as a `<Kbd>` suffix.
7. **Toast** (new, `components/ui/toast.tsx`): module-level zustand store (`toasts: ToastItem[]`) so the imperative `toast(opts)` API works outside React (e.g. mutation callbacks).
   - `toast({ title, description?, variant?: 'default'|'success'|'error'|'warning', duration? = 5000, action?: { label, onClick } }) → id`; `dismissToast(id)`.
   - `<Toaster/>` viewport (mounted once in `app/providers.tsx`): fixed bottom-right, stack of max 4 (oldest auto-evicted), each toast `role="status"` in an `aria-live="polite"` region (`variant='error'` → `role="alert"`); timers pause on hover; enter/exit via CSS transitions; variant icon + left border in the status color.
8. **Skeleton** (modified): `bg-surface-2`, adds `Skeleton.Text` convenience (n lines).
9. **EmptyState** (new): `<EmptyState icon={LucideIcon} title body? actions?>` — centered, dashed `border-border` container, primary/secondary action buttons. This is the shared substrate WS7-4 asks for; feature specs supply their CTAs.
10. **Badge** (new): variants `neutral | success | warn | danger | info | accent | outline`, sizes `sm | md`; `bg-*-bg text-*` recipe; optional `dot` prop. Replaces ad-hoc status pill maps as feature specs migrate.
11. **Kbd** (new): `<Kbd keys="mod+k"/>` — renders platform-aware (`⌘K` on mac, `Ctrl K` otherwise) via `lib/shortcuts/keys.ts` formatting.
12. **DiffText** (new): `<DiffText before after mode='words'|'chars'>` inline diff for tracked-changes UX (WS4) and patch summaries.
    - Algorithm: tokenize on `/(\s+)/` (words+whitespace preserved); LCS via O(n·m) DP with a guard `n*m ≤ 250_000` — over budget renders `<del>before</del><ins>after</ins>` wholesale; emit runs of `equal | del | ins`; render `<del>` (`bg-danger-bg text-danger line-through decoration-danger/50`) and `<ins>` (`bg-success-bg text-success`), both with `no-underline` semantics preserved for screen readers (native del/ins elements).
13. **Card / Label** (modified): retokened only.

### D4. Command palette + registry (`lib/command`, `components/command`)

**Registry** (`lib/command/registry.ts`, zustand — the extensibility API other specs push into):

```ts
export type CommandSection = 'navigate' | 'action' | 'theme' | 'file' | 'paper' | 'run';
export interface CommandContext {
  router: { push(href: string): void };
  projectId: string | null;
  queryClient: QueryClient;
  close(): void;
}
export interface Command {
  id: string;                    // unique, e.g. 'nav.ide', 'ide.save-active'
  title: string;                 // already-localized (registrants re-register on locale change)
  section: CommandSection;
  keywords?: string[];
  icon?: ComponentType<{ className?: string }>;
  shortcut?: string;             // 'mod+k' | 'mod+s' | 'g i' — display + shortcut-layer binding
  enabled?: (ctx: CommandContext) => boolean;   // hidden when false
  run: (ctx: CommandContext) => void | Promise<void>;
}
export function registerCommand(cmd: Command): () => void;      // returns unregister
export function registerCommands(cmds: Command[]): () => void;
export const useCommandStore: /* zustand */;                    // { commands: Map<string, Command>, open, setOpen }
export function useRegisterCommands(factory: () => Command[], deps: unknown[]): void; // effect helper: register on mount/deps change, unregister on cleanup
```

Duplicate `id` re-registration replaces (last-write-wins) so hot reload and locale re-registration are safe.

**Built-in commands** (registered by `useBuiltinCommands()` inside the workspace layout, re-run on `[t, projectId]`): navigate to Projects/Overview/Research/IDE/Experiments/Paper/Skills/Skill Builder/Settings (`g`-sequences as shortcuts: `g j / g o / g r / g i / g e / g p / g k / g b / g s`), theme: light/dark/system (section `theme`), "Switch language", "Sign out", "Open shortcuts help" (`?`). Project-scoped nav commands set `enabled: ctx => !!ctx.projectId`. **Dynamic navigation**: a provider reads `queryClient.getQueriesData({ queryKey: ['projects'] })` at palette-open time and emits "Open project: {name}" commands (section `navigate`) — read-only cache access, no coupling to feature files. File/paper providers are *not* built here; feature specs push them via `registerCommand` (documented in DESIGN_TOKENS.md §palette).

**Fuzzy filter** (`lib/command/fuzzy.ts`, pure, unit-testable):
`score(query, target): number | null` — case-insensitive subsequence match; `null` if not a subsequence; score = `100 + 20·(match starts at 0) + 10·(count of matches at word boundaries) − 1·(gap count) − 0.1·target.length`. A command's score = max over `title` and each keyword (keywords scored ×0.9). Empty query → all commands, grouped by section in registration order.

**Palette UI** (`components/command/CommandPalette.tsx`): Dialog-based (reuses D3.3 `<dialog>`), top-of-screen sheet (`max-w-xl`, `shadow-elev3`), search input with `role="combobox"` + `aria-controls`/`aria-activedescendant`; results `role="listbox"` grouped by section (top 8 per section), `ArrowUp/Down` moves the active item across groups, `Enter` runs + closes, `Esc` closes; each row shows icon, title, and `<Kbd>` when `shortcut` present. MRU boost (STRETCH): last 10 executed ids in localStorage `ros-cmd-mru`, +15 score. Open state lives in the command store so `mod+k`, the TopBar button, and `close()` in `CommandContext` share it.

### D5. Global shortcut layer (`lib/shortcuts`)

`lib/shortcuts/keys.ts`: `parseChord('mod+k') → { key, ctrl, meta, alt, shift }` with `mod` resolved by platform (`navigator.platform` sniff, cached); `formatChord('mod+k') → '⌘K' | 'Ctrl K'`; `isEditableTarget(el)` → true for `INPUT/TEXTAREA/SELECT`, `isContentEditable`, or `el.closest('.monaco-editor')`.

`lib/shortcuts/index.tsx`: `<ShortcutProvider>` (mounted in `app/(workspace)/layout.tsx`) installs **one** window `keydown` listener:

1. Build the binding table from the command registry each event (cheap map scan): commands with `shortcut` split into **chords** (`mod+k`, `mod+s`, `mod+enter`, `?`) and **sequences** (`g <letter>`).
2. Chord handling: chords containing `mod` fire even in editable targets (`mod+s` must `preventDefault` to suppress browser save); bare-key chords (`?`) are ignored in editable targets.
3. Sequence handling: on bare `g` (not editable target), set `pending='g'` + 1200ms timeout + a subtle "g …" hint chip (bottom-left, aria-hidden); next keypress matched against `g x` bindings; any non-match clears pending.
4. Matched command → `run(ctx)` with the same `CommandContext` as the palette (single source of truth — the cheatsheet renders *from the registry*, so docs never drift).
5. `mod+s` / `mod+enter` have **no built-in behavior**; they execute whatever command a feature spec registered with that shortcut (e.g. IDE spec registers `ide.save-active` with `shortcut: 'mod+s'`, `enabled` only on the IDE route). Collisions: last registration wins (same as registry rule).

`components/command/ShortcutCheatsheet.tsx`: Dialog listing all registered commands that have shortcuts, grouped by section, rendered with `<Kbd>`; opened by `?` or the palette command.

### D6. Workspace shell polish (`features/workspace`, `app/(workspace)/layout.tsx`)

1. **TopBar**: left — app wordmark (links `/projects`), `OrgSwitcher`, new `ProjectSwitcher`; right — palette button (`Search` icon + `⌘K` Kbd, opens palette), `ThemeToggle`, `LanguageSwitcher`, `UserMenu`. All tokens; height stays `h-14`; `bg-surface/95 backdrop-blur border-b border-border`.
2. **ThemeToggle** (`features/workspace/ThemeToggle.tsx`): icon Button (Sun/Moon/Monitor per preference) opening a Dropdown with three `DropdownRadioItem`s (light/dark/system, localized); tooltip "Theme".
3. **UserMenu**: Dropdown from an avatar button (initials circle, `bg-accent text-accent-fg`); items: display name + email (DropdownLabel), separator, Settings (project-scoped, hidden without project), Sign out (destructive, moves `logoutMutation` here from `TopBar.tsx:18-21`).
4. **ProjectSwitcher** (new): Dropdown showing current project name (derived from route param + `['projects']` query cache; falls back to fetching `listProjects(orgId)` via the existing `lib/api/projects` import — read-only usage of a non-owned module is allowed); items navigate to the same sub-page in the target project (regex-swap the `projectId` segment of `pathname`, falling back to `/overview`); footer item "All projects → /projects". Hidden when route has no `projectId`.
5. **OrgSwitcher**: rebuilt on Dropdown (keeps `useWorkspaceStore` read/write exactly as `OrgSwitcher.tsx:9-17`, file untouched elsewhere): org initial avatar + name + role Badge per item; keeps the first-org defaulting effect verbatim.
6. **LanguageSwitcher**: rebuilt on Dropdown (Languages icon); on change also fire-and-forget `PUT /users/me/preferences {"locale": next}` through a helper in `lib/theme/preferences.ts` (shared preferences client, since `lib/api/**` is outside this partition).
7. **SideRail**: lucide icons replace emoji (`LayoutDashboard, Search, Code2, FlaskConical, FileText, Puzzle, Hammer, Settings, FolderKanban`); active state `bg-accent text-accent-fg` with exact-segment matching fixed (`pathname.startsWith(href)` at `SideRail.tsx:36` wrongly lights "Skills" on `/skills/builder` — compare against path-with-boundary: active iff `pathname === href || pathname.startsWith(href + '/')`, and compute the *longest* matching item so `skills/builder` wins over `skills`); disabled items keep `aria-disabled`; each item wrapped in Tooltip showing its `g x` shortcut; STRETCH: collapse-to-icons toggle persisted in `localStorage ros-siderail` (local state — `lib/store/ui.ts` is not owned).
8. **Workspace layout**: mounts `ShortcutProvider`, `CommandPalette`, `ShortcutCheatsheet`; retokens the skeleton/loading frame; keeps the session/401 logic at `layout.tsx:17-21` byte-identical.
9. **Auth layout + register page**: retoken; i18n-ify the register page's hardcoded strings (`auth.*` keys already exist; add missing ones).
10. **Settings page**: add an **Appearance** card above Language: three radio tiles (light/dark/system) each with a 64×40 mini mock preview (pure divs in fixed hex colors), wired to `useTheme()`; retoken the rest of the page. LLM card DOM structure untouched otherwise (feature-y but the file is `app/**`-owned; keep the diff minimal).
11. **`app/error.tsx` + `app/not-found.tsx` + `app/(workspace)/projects/[projectId]/loading.tsx`** (new): token-styled EmptyState-based pages (error page shows `error.digest` + retry button calling `reset()`).

### D7. i18n additions

1. `t(key, params?)` interpolation: `'{name}'` placeholders replaced via single-pass regex; signature `t(key: DictKey, params?: Record<string, string | number>)` — backward compatible.
2. New keys (added to **both** dictionaries; parity is compile-enforced by `Record<DictKey, string>`):
   `common.close, common.confirm, common.search, common.copy, common.copied, common.openMenu, common.signedInAs`
   `theme.label, theme.light, theme.dark, theme.system`
   `palette.placeholder, palette.empty, palette.sectionNavigate, palette.sectionAction, palette.sectionTheme, palette.sectionFile, palette.sectionPaper, palette.sectionRun, palette.openProject, palette.hint`
   `shortcuts.title, shortcuts.pressG, shortcuts.help`
   `nav.allProjects, nav.switchProject, nav.currentProject`
   `toast.dismiss`
   `settings.appearance, settings.appearanceHint`
   `errors.title, errors.body, errors.retry, errors.notFoundTitle, errors.notFoundBody, errors.backHome`
   `emptyState.defaultTitle`
   plus any `auth.*` keys the register page needs. (~45 keys × 2 locales.)
3. The boot script stamps `<html lang>` pre-paint (D2.1); `setLocale` keeps updating it (`lib/i18n/index.tsx:37` behavior preserved).

### D8. DESIGN_TOKENS.md (deliverable for other implementers)

Sections: (1) token table (name → tailwind class → light/dark values → usage rule); (2) elevation & radii; (3) **migration mapping** for feature specs: `bg-white → bg-surface`, `bg-neutral-50 → bg-bg or bg-surface-2`, `border-neutral-200 → border-border`, `border-neutral-300 → border-border-strong`, `text-neutral-900 → text-text`, `text-neutral-500/400 → text-muted/text-faint`, `bg-neutral-900+text-white → bg-accent+text-accent-fg`, amber/emerald/red pills → `<Badge variant=warn|success|danger>`; (4) primitive catalog with props + do/don't (e.g. "never hand-roll a modal — use Dialog"); (5) command registration guide with a worked example (`useRegisterCommands`); (6) toast usage; (7) Monaco/charts theming imports; (8) statement that the neutral-ramp compat layer is transitional + removal criterion; (9) a11y checklist (focus ring, aria patterns baked into primitives).

---

## API contract changes

**None owned by this spec** (frontend-only partition). It *consumes* one new endpoint pair owned by the experiments-figures spec — exact contract requested in Cross-partition requests:

```
GET /users/me/preferences
→ 200 {"theme": "light"|"dark"|"system", "locale": "zh-CN"|"en-US"|null, "figure_style_slug": string|null}
→ 401 standard error envelope

PUT /users/me/preferences        (CSRF header required; partial update — omitted fields unchanged)
body: {"theme": "dark"}  or  {"locale": "en-US"}
→ 200 full preferences object (as GET)
→ 422 {"error":{"code":"validation_error",...}} on bad enum value
```

Frontend degradation: all preference calls are fire-and-forget/best-effort; `404` (endpoint not yet landed), `401`, and network failures are swallowed — localStorage remains authoritative on-device, so this spec is fully functional standalone.

## WS events

None. (No new event producers or consumers; the palette/shortcuts/theme are purely client-side.)

## DB changes

None. (The `user_preferences` storage belongs to the experiments-figures spec per the workstream brief.)

## shared-schemas additions

For the consolidation agent — one type, no events:

```ts
// packages/shared-schemas/src/preferences.ts
export type ThemePreference = 'light' | 'dark' | 'system';
export interface UserPreferences {
  theme: ThemePreference;
  locale: 'zh-CN' | 'en-US' | null;
  figure_style_slug: string | null;
}
```

Until consolidated, `lib/theme/preferences.ts` declares these types locally (structurally identical) to stay buildable; swap to the shared import is a follow-up one-liner.

## New dependencies

- `apps/web/package.json` dependencies: **`lucide-react` `^0.4xx`** (tree-shaken icon components; explicitly allowed by the brief). Nothing else at runtime.
- devDependencies (SHOULD): **`vitest` `^2.x`** for pure-function unit tests (fuzzy scorer, DiffText LCS, chord parser) with a `test:unit` script (`vitest run`, node environment, no jsdom needed — all three modules are DOM-free). If the implementer must cut, drop vitest and rely on Playwright + tsc.
- No Python deps.

---

## File-by-file plan

**Modified — app shell & config**
| File | Change |
|---|---|
| `apps/web/tailwind.config.ts` | Semantic color/radius/shadow mapping; neutral-ramp + `white` compat override; `darkMode: ['selector','[data-theme="dark"]']`; `fontFamily.sans` from CSS var. |
| `apps/web/app/globals.css` | Full rewrite: token blocks (`:root`, `:root[data-theme="dark"]`), gray compat ramp, base styles, scrollbar, focus ring, kbd, dialog backdrop, reduced-motion, dark select-chevron. Delete lines 15-17 (light-mode force). |
| `apps/web/app/layout.tsx` | Inline theme+lang boot script in `<head>`; `<html suppressHydrationWarning>` (lang stamped by script). |
| `apps/web/app/providers.tsx` | Wrap children with `ThemeProvider`; mount `<Toaster/>`. |
| `apps/web/app/(workspace)/layout.tsx` | Mount `ShortcutProvider` + `CommandPalette` + `ShortcutCheatsheet`; retoken; session logic untouched. |
| `apps/web/app/(auth)/layout.tsx` | Retoken (gradient → `from-bg via-surface to-surface-2`). |
| `apps/web/app/(auth)/login/page.tsx`, `register/page.tsx` | Retoken; i18n-ify register strings. |
| `apps/web/app/(workspace)/projects/page.tsx` and `[projectId]/{overview,research,ide,experiments,paper,skills,skills/builder}/page.tsx` | Page-level class sweep only (`border-neutral-200 → border-border`, `bg-white → bg-surface`, etc.); feature components inside untouched. |
| `apps/web/app/(workspace)/projects/[projectId]/settings/page.tsx` | Add Appearance card; retoken. |

**Created — app**
`apps/web/app/error.tsx`, `apps/web/app/not-found.tsx`, `apps/web/app/(workspace)/projects/[projectId]/loading.tsx`.

**Modified — components/ui**: `button.tsx` (variants/sizes/loading + tokens), `input.tsx`, `card.tsx`, `label.tsx`, `skeleton.tsx` (tokens).

**Created — components**: `components/ui/textarea.tsx`, `dialog.tsx`, `dropdown.tsx`, `tabs.tsx`, `tooltip.tsx`, `toast.tsx` (+`Toaster`), `badge.tsx`, `empty-state.tsx`, `kbd.tsx`, `diff-text.tsx`; `components/command/CommandPalette.tsx`, `components/command/ShortcutCheatsheet.tsx`; `components/editor/monaco.tsx` (themed Monaco/Diff wrappers).

**Modified — features/workspace**: `TopBar.tsx` (recomposed), `SideRail.tsx` (icons, active-match fix, tooltips), `OrgSwitcher.tsx` (Dropdown rebuild), `LanguageSwitcher.tsx` (Dropdown rebuild + preference sync).
**Created — features/workspace**: `ThemeToggle.tsx`, `UserMenu.tsx`, `ProjectSwitcher.tsx`.

**Created — lib**: `lib/theme/index.tsx`, `lib/theme/monaco.ts`, `lib/theme/charts.ts`, `lib/theme/preferences.ts`; `lib/shortcuts/index.tsx`, `lib/shortcuts/keys.ts`; `lib/command/registry.ts`, `lib/command/fuzzy.ts`, `lib/command/builtin.tsx`.
**Modified — lib/i18n**: `index.tsx` (interpolation), `dictionaries/zh-CN.ts` + `en-US.ts` (~45 keys each).

**Created — tests**: `apps/web/e2e/design-system.spec.ts` (theme/palette/shortcuts/toast); SHOULD: `apps/web/lib/command/fuzzy.test.ts`, `apps/web/components/ui/diff-text.test.ts`, `apps/web/lib/shortcuts/keys.test.ts` (vitest).

**Created — docs**: `docs/DESIGN_TOKENS.md`.

**Deleted**: none (`lib/ide/monaco.tsx` stays until its owner swaps imports; deleting it would break non-owned files).

Estimated churn ≈ 2,300 added/changed lines including docs — within budget; SHOULD/STRETCH items are the release valve.

---

## Cross-partition requests

1. **experiments-figures spec (preferences backend)** — implement exactly:
   `GET /users/me/preferences` and `PUT /users/me/preferences` per the contract above (session-auth, CSRF on PUT, partial update, unknown fields rejected 422, table keyed by `user_id` with `theme text default 'system'`, `locale text null`, `figure_style_slug text null`). Nothing in this spec blocks on it (graceful 404 handling).
2. **ide-coding spec** — in `features/ide/EditorPane.tsx:9` and `features/ide/PatchDiff.tsx:8`: change `import { MonacoEditor/MonacoDiff } from '@/lib/ide/monaco'` → `from '@/components/editor/monaco'` (no other change; `theme` handled internally). Optionally register palette commands (`ide.save-active` with `shortcut:'mod+s'`, "New coding request") via `useRegisterCommands` from `@/lib/command/registry`.
3. **paper spec** — same import swap in `features/paper/PaperWorkspace.tsx:9`; optionally register `paper.compile` command.
4. **experiments spec** — `features/experiments/MetricsChart.tsx`: replace `COLORS` (line 21) and hex grid/axis (lines 55-57) with `const { colors, grid, axis, tooltip } = useChartTheme()` from `@/lib/theme/charts`.
5. **shared-schemas consolidator** — add `preferences.ts` exports listed above; re-export from the package index.
6. **All feature specs (non-blocking, via DESIGN_TOKENS.md)** — restyle owned files per the migration mapping; use `Dialog/Toast/EmptyState/Badge` instead of hand-rolled equivalents (`features/projects/CreateProjectDialog.tsx` owner: rebuild on `Dialog`); push dynamic palette commands (files/papers/runs) via `registerCommand`.

---

## MUST / SHOULD / STRETCH breakdown

**MUST** (core, spec fails without): D1 tokens + tailwind mapping + compat ramp + globals rewrite; D2 boot script + ThemeProvider + localStorage persistence + preferences fire-and-forget; `lib/theme/monaco.ts` + `components/editor/monaco.tsx` + `lib/theme/charts.ts`; primitives Button/Input/Textarea/Dialog/Toast+Toaster/Badge/Skeleton/EmptyState/Kbd; D4 registry + fuzzy + palette UI + built-in nav/theme commands; D5 shortcut layer with `mod+k` and `g`-sequences; TopBar (ThemeToggle, UserMenu, palette button) + SideRail (icons, active-fix); i18n interpolation + all new keys; `docs/DESIGN_TOKENS.md`.

**SHOULD**: Dropdown-based OrgSwitcher/LanguageSwitcher rebuilds; ProjectSwitcher; Tabs; Tooltip (fall back to `title=` attributes if cut); DiffText; Settings Appearance card; `error.tsx`/`not-found.tsx`/`loading.tsx`; ShortcutCheatsheet (`?`); preferences sync-down on fresh browsers; vitest unit tests; register-page i18n.

**STRETCH**: palette MRU boost; "Open project" dynamic commands from query cache; SideRail collapse mode; toast hover-pause polish; `g`-pending hint chip.

Degradation rule: cutting any SHOULD/STRETCH item must not leave dead i18n keys or dead exports (tsc-clean at every cut point).

---

## Acceptance criteria (verifiable with local gates or by reading code/UI)

1. `pnpm --filter web typecheck` and `pnpm --filter web build` pass (tsc + next build are the binding gates).
2. `globals.css` contains both `:root` and `:root[data-theme="dark"]` blocks defining every token in the D1 table, and no `color-scheme: light` force under a dark media query.
3. `tailwind.config.ts` maps all semantic colors via `rgb(var(--…) / <alpha-value>)`, overrides `neutral`/`white` to the compat ramp, and sets `darkMode: ['selector', '[data-theme="dark"]']`.
4. `grep -RE "neutral-|bg-white|text-white" apps/web/components apps/web/features/workspace apps/web/app --include='*.tsx'` → 0 matches (owned shell fully on tokens; compat ramp exists only in config/css).
5. `app/layout.tsx` renders the inline boot script before body content and `<html suppressHydrationWarning>`; script handles absent localStorage via try/catch (read the code).
6. `components/ui/dialog.tsx` uses a native `<dialog>` (`grep showModal`) — no focus-trap library; `dropdown.tsx` implements `role="menu"` + arrow-key roving focus; `toast.tsx` renders `aria-live` region; palette input has `role="combobox"` with `aria-activedescendant`.
7. `lib/command/registry.ts` exports `registerCommand` returning an unregister function; built-ins register ≥ 12 commands; the cheatsheet renders from the registry (no hardcoded shortcut list).
8. `package.json` gains only `lucide-react` (+ optional `vitest` devDep); no Radix/cmdk/headlessui/framer-motion.
9. All new UI strings resolve through `t()`; adding a key to `zh-CN.ts` without `en-US.ts` fails `tsc` (existing `Record<DictKey,string>` typing — verify by reading both dicts).
10. `docs/DESIGN_TOKENS.md` exists with the token table, migration mapping, primitive catalog, and command-registration example.
11. Preference calls are wrapped so a 404 never surfaces to the UI (read `lib/theme/preferences.ts` — every call in try/catch or `.catch(() => {})`).
12. No mock-LLM impact: zero agent modes introduced (nothing to extend in the mock provider).

## Test plan (CI-run; no external network)

**Playwright (`apps/web/e2e/design-system.spec.ts`, runs against the seeded demo stack like `e2e/smoke.spec.ts`):**
1. *Theme*: login → click ThemeToggle → choose Dark → `expect(html).toHaveAttribute('data-theme','dark')` → reload → attribute persists (localStorage path; no backend dependency).
2. *FOUC guard*: `page.addInitScript` sets `ros-theme=dark`, navigate, assert `data-theme='dark'` before any client JS settles (evaluate on `domcontentloaded`).
3. *Palette*: press `Control+K` → combobox visible → type `ide` → first option is the IDE nav command → `Enter` → URL matches `/projects/.*/ide`.
4. *Sequences*: press `g` then `e` on the overview page → URL matches `/experiments`; typing `g` inside the palette input does **not** navigate.
5. *Dialog a11y*: open palette, `Esc` closes, focus returns to the previously focused element.
6. *Toast*: `page.evaluate` a `toast({title})` call via a test hook (Toaster exposes `window.__rosToast` in dev builds only — guarded by `process.env.NODE_ENV !== 'production'`) → `role=status` visible → auto-dismisses.
**Vitest (SHOULD, pure node)**: fuzzy scorer (subsequence, prefix/boundary bonuses, null on non-match, keyword penalty); DiffText LCS (equal/ins/del runs, budget fallback); `parseChord`/`formatChord` (mod resolution both platforms).
**pytest**: none — this partition changes no Python. (Stated explicitly per constraints.)

## Explicitly out of scope

- Restyling feature directories (`features/ide|research|experiments|paper|projects|skills|auth|system`) — their specs consume DESIGN_TOKENS.md; the compat ramp keeps them presentable in dark mode meanwhile.
- The preferences backend (endpoint, table, migration) — experiments-figures spec.
- Run inspector (WS7-3) and onboarding checklist (WS7-4) — this spec ships their substrate (Dialog/EmptyState/Badge) only.
- WS reconnect/client fixes (`lib/websocket/**`), API client hardening (`lib/api/client.ts`), route-guard loop fix (`middleware.ts`) — other partitions.
- Monaco offline bundling (P3-D13 stands), `lib/store/**` changes, `packages/ui` extraction, Storybook, visual-regression tooling.
- Deleting `lib/ide/monaco.tsx` (owned elsewhere; removal happens after import swaps land).
