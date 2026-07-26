'use client';

/**
 * Deterministic figure-style thumbnail (partition: frontend-paper, Design G.3).
 *
 * A pure inline SVG mini line-chart (2 series, 12 fixed points) rendered from a
 * preset's `style` object — no server rendering, fully offline. Drives the
 * figure-style gallery tiles in PreferencesSection and the dialog style pickers.
 */

import type { StylePresetStyle } from '@/lib/api/figures';

// Twelve fixed points per series, normalized to [0,1]; deterministic across runs.
const SERIES_A = [0.15, 0.28, 0.22, 0.4, 0.52, 0.48, 0.6, 0.68, 0.62, 0.75, 0.82, 0.9];
const SERIES_B = [0.6, 0.55, 0.62, 0.5, 0.44, 0.5, 0.4, 0.36, 0.42, 0.3, 0.26, 0.2];

function polyline(points: number[], w: number, h: number, pad: number): string {
  const innerW = w - pad * 2;
  const innerH = h - pad * 2;
  return points
    .map((v, i) => {
      const x = pad + (innerW * i) / (points.length - 1);
      const y = pad + innerH * (1 - v);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');
}

export function FigureStyleThumb({
  style,
  width = 132,
  height = 84,
}: {
  style: StylePresetStyle;
  width?: number;
  height?: number;
}) {
  const pad = 8;
  const [c0, c1] = [style.palette[0] ?? '#4C72B0', style.palette[1] ?? '#DD8452'];
  const gridStroke = 'rgb(var(--color-border) / 0.9)';
  const axisStroke = 'rgb(var(--color-border-strong) / 0.9)';

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="img"
      aria-hidden="true"
      style={{ fontFamily: style.font_family === 'serif' ? 'serif' : 'sans-serif' }}
    >
      <rect x={0} y={0} width={width} height={height} rx={4} fill="rgb(var(--color-surface))" />
      {style.grid &&
        [0.25, 0.5, 0.75].map((f) => (
          <line
            key={f}
            x1={pad}
            x2={width - pad}
            y1={pad + (height - pad * 2) * f}
            y2={pad + (height - pad * 2) * f}
            stroke={gridStroke}
            strokeWidth={0.5}
          />
        ))}
      {/* axes */}
      <line x1={pad} y1={height - pad} x2={width - pad} y2={height - pad} stroke={axisStroke} strokeWidth={0.75} />
      <line x1={pad} y1={pad} x2={pad} y2={height - pad} stroke={axisStroke} strokeWidth={0.75} />
      <polyline points={polyline(SERIES_A, width, height, pad)} fill="none" stroke={c0} strokeWidth={1.5} />
      <polyline points={polyline(SERIES_B, width, height, pad)} fill="none" stroke={c1} strokeWidth={1.5} />
      {/* legend swatches */}
      <g>
        {style.legend_frame && (
          <rect
            x={width - 34}
            y={pad + 1}
            width={30}
            height={16}
            rx={2}
            fill="rgb(var(--color-surface))"
            stroke={axisStroke}
            strokeWidth={0.5}
          />
        )}
        <rect x={width - 31} y={pad + 4} width={6} height={2} fill={c0} />
        <rect x={width - 31} y={pad + 10} width={6} height={2} fill={c1} />
      </g>
    </svg>
  );
}
