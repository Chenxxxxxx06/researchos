'use client';

import { useQuery } from '@tanstack/react-query';
import { Activity, CloudOff } from 'lucide-react';

import { Tooltip } from '@/components/ui/tooltip';
import { getReadiness, type ReadinessResponse } from '@/lib/api/client';
import { cn } from '@/lib/utils';

export function RuntimeStatus() {
  const readiness = useQuery<ReadinessResponse>({
    queryKey: ['readiness'],
    queryFn: getReadiness,
    refetchInterval: 30_000,
    retry: 1,
  });
  const healthy = readiness.data?.status === 'ok';
  const label = readiness.isLoading
    ? '正在检查运行环境'
    : readiness.isError
      ? '运行环境不可用'
      : healthy
        ? '运行环境正常'
        : '部分服务异常';
  const Icon = readiness.isError ? CloudOff : Activity;

  return (
    <Tooltip content={label} side="bottom">
      <button
        type="button"
        onClick={() => void readiness.refetch()}
        aria-label={label}
        className={cn(
          'desktop-no-drag hidden h-8 items-center gap-2 rounded-md border px-2.5 text-[11px] font-medium xl:flex',
          healthy
            ? 'border-success/20 bg-success-bg/55 text-success'
            : readiness.isError
              ? 'border-danger/20 bg-danger-bg text-danger'
              : 'border-warn/20 bg-warn-bg text-warn',
        )}
      >
        <Icon className={cn('h-3.5 w-3.5', readiness.isLoading && 'animate-pulse')} aria-hidden="true" />
        <span>{healthy ? 'Runtime ready' : readiness.isLoading ? 'Checking' : 'Runtime issue'}</span>
      </button>
    </Tooltip>
  );
}
