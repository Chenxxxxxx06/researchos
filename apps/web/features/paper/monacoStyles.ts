/**
 * Monaco decoration CSS injected at runtime (partition: frontend-paper).
 *
 * Editor decorations reference document-level CSS classes; `app/globals.css` is
 * design-system-owned, so this partition injects its own <style> once. Colors
 * reference the semantic token CSS variables (space-separated RGB triplets) so
 * decorations stay theme-aware in both light and dark.
 */

const STYLE_ID = 'ros-paper-monaco-decorations';

const CSS = `
.ros-strike {
  text-decoration: line-through;
  text-decoration-color: rgb(var(--color-danger) / 0.8);
  background: rgb(var(--color-danger) / 0.12);
}
.ros-suggest-range {
  background: rgb(var(--color-accent) / 0.10);
  border-radius: 2px;
}
.ros-stale-gutter {
  background: rgb(var(--color-warn) / 0.9);
  width: 6px !important;
  height: 6px !important;
  margin: 7px 0 0 4px;
  border-radius: 9999px;
}
`;

/** Idempotently ensure the decoration styles exist in <head>. */
export function ensurePaperDecorationStyles(): void {
  if (typeof document === 'undefined') return;
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = STYLE_ID;
  style.textContent = CSS;
  document.head.appendChild(style);
}
