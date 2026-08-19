# ResearchOS Design System V2

## Design read

Professional research cockpit for daily technical work. The interface is calm, evidence-led, compact, and operational rather than decorative.

- Design variance: 4
- Motion intensity: 3
- Visual density: 7

## Foundations

ResearchOS keeps the existing Tailwind CSS v3 semantic-token architecture and owned UI primitives. It does not introduce a second component system or ship default shadcn styling.

## Typography

- Product sans: self-hosted Geist Sans
- Code and numeric data: Geist Mono
- CJK fallback: PingFang SC, Microsoft YaHei UI, Microsoft YaHei
- Page title: 28px to 36px
- Section title: 16px to 22px
- Body: 13px to 14px
- Metadata: 11px to 12px
- 9px and 10px are reserved for IDs or dense machine metadata

## Color

The palette uses cool research neutrals and one forest-green accent.

Green is reserved for primary actions, selected evidence, and verified state. Warning, danger, and information use semantic colors. Decorative green status dots are not permitted.

Light and dark themes share the same hierarchy:

- `bg`: application canvas
- `surface`: primary panels
- `surface-2`: hover and nested surfaces
- `surface-3`: progress tracks and strong nested surfaces
- `overlay`: menus and dialogs
- `border`: passive separators
- `border-strong`: controls and emphasized boundaries

## Shape system

- Small control: 6px
- Standard control: 10px
- Workspace panel: 14px
- Fully rounded shapes are limited to status badges and avatars

## Workspace hierarchy

1. Shell
2. Context panel
3. Primary work surface
4. Inspector
5. Overlay

A panel may use a border and a subtle tinted shadow. Nested cards should normally use spacing or one separator instead of another shadow.

## Motion

- Hover and press feedback: 120ms to 160ms
- Panel transitions: 160ms to 200ms
- Animate transform and opacity only
- Live Agent and experiment states may pulse only when the state is real
- All motion honors reduced-motion preferences

## Responsive targets

- 1280x720 small desktop
- 1440x900 standard laptop
- 1920x1080 workstation
- 390x844 mobile status and review surfaces

Heavy Monaco and experiment workspaces prioritize desktop. Mobile views must remain navigable and must not render several fixed-width panes side by side.

## State completeness

Every data surface defines loading, empty, error, success, reconnecting, and permission-denied states. Skeletons remain local to the data region and never replace the complete application shell.
