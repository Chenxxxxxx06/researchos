'use client';

import { useQuery } from '@tanstack/react-query';

import { getReadiness, type ReadinessResponse } from '@/lib/api/client';

/**
 * System status panel.
 *
 * Demonstrates frontend <-> backend connectivity and the four required UI
 * states: loading, error, empty, and success.
 */
export function SystemStatus() {
  const { data, isLoading, isError, error } = useQuery<ReadinessResponse>({
    queryKey: ['readiness'],
    queryFn: getReadiness,
  });

  if (isLoading) {
    return <StatusShell title="Checking backend...">
      <p className="text-sm text-neutral-500">Contacting the ResearchOS API.</p>
    </StatusShell>;
  }

  if (isError) {
    return (
      <StatusShell title="Backend unreachable" tone="error">
        <p className="text-sm text-red-600">
          {error instanceof Error ? error.message : 'Unknown error'}
        </p>
        <p className="mt-2 text-xs text-neutral-500">
          Is the API running on the configured base URL?
        </p>
      </StatusShell>
    );
  }

  if (!data || data.checks.length === 0) {
    return (
      <StatusShell title="No status reported">
        <p className="text-sm text-neutral-500">The readiness endpoint returned no checks.</p>
      </StatusShell>
    );
  }

  const ok = data.status === 'ok';
  return (
    <StatusShell
      title={ok ? 'All systems operational' : 'Degraded'}
      tone={ok ? 'ok' : 'error'}
    >
      <ul className="mt-2 space-y-1">
        {data.checks.map((check) => (
          <li key={check.name} className="flex items-center justify-between text-sm">
            <span className="font-mono text-neutral-700">{check.name}</span>
            <span
              className={
                check.status === 'ok'
                  ? 'rounded bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700'
                  : 'rounded bg-red-100 px-2 py-0.5 text-xs font-medium text-red-700'
              }
              title={check.detail ?? undefined}
            >
              {check.status}
            </span>
          </li>
        ))}
      </ul>
    </StatusShell>
  );
}

function StatusShell({
  title,
  tone = 'neutral',
  children,
}: {
  title: string;
  tone?: 'neutral' | 'ok' | 'error';
  children: React.ReactNode;
}) {
  const dot =
    tone === 'ok' ? 'bg-green-500' : tone === 'error' ? 'bg-red-500' : 'bg-neutral-400';
  return (
    <div className="w-full max-w-md rounded-lg border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2">
        <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
        <h2 className="text-base font-semibold">{title}</h2>
      </div>
      <div className="mt-2">{children}</div>
    </div>
  );
}
