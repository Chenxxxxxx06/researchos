'use client';

import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { Skeleton } from '@/components/ui/skeleton';
import { listMetrics, type Metric } from '@/lib/api/experiments';
import { ApiError } from '@/lib/api/client';
import { useI18n } from '@/lib/i18n';

const COLORS = ['#2563eb', '#16a34a', '#dc2626', '#d97706', '#7c3aed', '#0891b2'];

type ChartPoint = { step: number } & Record<string, number>;

function buildSeries(metrics: Metric[]): { points: ChartPoint[]; names: string[] } {
  const names = Array.from(new Set(metrics.map((m) => m.name)));
  const byStep = new Map<number, ChartPoint>();

  for (const metric of metrics) {
    const point = byStep.get(metric.step) ?? ({ step: metric.step } as ChartPoint);
    point[metric.name] = metric.value;
    byStep.set(metric.step, point);
  }

  const points = Array.from(byStep.values()).sort((a, b) => a.step - b.step);
  return { points, names };
}

export function MetricsChart({ projectId, runId }: { projectId: string; runId: string }) {
  const { t } = useI18n();
  const { data, isLoading, isError } = useQuery<Metric[], ApiError>({
    queryKey: ['metrics', projectId, runId],
    queryFn: () => listMetrics(projectId, runId),
  });

  const { points, names } = useMemo(() => buildSeries(data ?? []), [data]);

  if (isLoading) return <Skeleton className="h-[240px] w-full" />;
  if (isError) return <p className="text-xs text-red-600">{t('common.error')}</p>;
  if (points.length === 0) return <p className="text-xs text-neutral-500">{t('common.empty')}</p>;

  return (
    <ResponsiveContainer width="100%" height={240}>
      <LineChart data={points} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e5e5" />
        <XAxis dataKey="step" tick={{ fontSize: 11 }} stroke="#a3a3a3" />
        <YAxis tick={{ fontSize: 11 }} stroke="#a3a3a3" />
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        {names.map((name, i) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={COLORS[i % COLORS.length]}
            dot={false}
            strokeWidth={2}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
