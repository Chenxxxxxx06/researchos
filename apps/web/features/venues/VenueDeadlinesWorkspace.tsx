'use client';

import { useQuery } from '@tanstack/react-query';
import { CalendarClock, ExternalLink, RefreshCw, Search } from 'lucide-react';
import { useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { listVenueDeadlines } from '@/lib/api/venues';

const CALENDAR_URL = 'https://ccfddl.com/conference/deadlines_zh.ics';
const REPOSITORY_URL = 'https://github.com/ccfddl/ccf-deadlines';

export function VenueDeadlinesWorkspace({ projectId }: { projectId: string }) {
  const [query, setQuery] = useState('');
  const [futureOnly, setFutureOnly] = useState(true);
  const deadlines = useQuery({
    queryKey: ['venue-deadlines', projectId],
    queryFn: () => listVenueDeadlines(projectId),
    staleTime: 30 * 60 * 1000,
  });
  const visible = useMemo(() => {
    const keyword = query.trim().toLowerCase();
    const now = Date.now();
    return (deadlines.data?.items ?? []).filter((item) => {
      if (futureOnly && new Date(item.starts_at).getTime() < now) return false;
      return !keyword || `${item.title} ${item.description ?? ''}`.toLowerCase().includes(keyword);
    });
  }, [deadlines.data, futureOnly, query]);

  return (
    <div className="-m-5 min-h-[calc(100vh-4rem)] bg-bg lg:-m-6 xl:-m-8">
      <header className="border-b border-border bg-surface px-6 py-4">
        <h1 className="flex items-center gap-2 text-lg font-semibold text-text">
          <CalendarClock className="h-5 w-5" /> 会议与期刊 DDL
        </h1>
        <p className="mt-1 text-sm text-muted">
          实时读取 CCFDDL 中文 iCal；ResearchOS 不保存或猜测截止日期，请提交前再次核对会议官网。
        </p>
      </header>

      <div className="space-y-5 p-6">
        <Card>
          <CardContent className="flex flex-wrap items-center gap-3">
            <div className="relative min-w-64 flex-1">
              <Search className="absolute left-3 top-3 h-4 w-4 text-faint" />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="筛选 NeurIPS、ICML、ACL、CVPR…"
                className="pl-9"
              />
            </div>
            <label className="flex items-center gap-2 text-sm text-muted">
              <input
                type="checkbox"
                checked={futureOnly}
                onChange={(event) => setFutureOnly(event.target.checked)}
              />
              仅显示未来事件
            </label>
            <Button variant="secondary" onClick={() => void deadlines.refetch()}>
              <RefreshCw className="h-4 w-4" /> 刷新
            </Button>
            <a
              href={CALENDAR_URL}
              className="inline-flex h-10 items-center gap-1.5 rounded-md border border-border-strong px-3 text-sm text-text hover:bg-surface-2"
            >
              订阅 iCal <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </CardContent>
        </Card>

        {deadlines.isLoading && <p className="text-sm text-muted">正在同步 CCFDDL…</p>}
        {deadlines.error && (
          <div className="rounded-lg border border-danger/30 bg-danger-bg p-4 text-sm text-danger">
            实时源暂时不可用：{deadlines.error instanceof Error ? deadlines.error.message : '未知错误'}。
            你仍可直接访问{' '}
            <a className="underline" href={REPOSITORY_URL} target="_blank" rel="noreferrer">
              ccfddl/ccf-deadlines
            </a>
            。
          </div>
        )}
        {deadlines.data && (
          <>
            <div className="flex items-center justify-between text-xs text-muted">
              <span>{visible.length} 个匹配事件</span>
              <span>
                来源：
                <a className="underline" href={REPOSITORY_URL} target="_blank" rel="noreferrer">
                  {deadlines.data.source_name}
                </a>
                {' · '}
                同步于 {new Date(deadlines.data.fetched_at).toLocaleString()}
              </span>
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              {visible.slice(0, 120).map((item) => (
                <Card key={item.uid}>
                  <CardHeader>
                    <CardTitle>{item.title}</CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-2">
                    <p className="text-base font-semibold text-accent">
                      {new Date(item.starts_at).toLocaleString()}
                    </p>
                    {item.location && <p className="text-xs text-muted">{item.location}</p>}
                    {item.description && (
                      <p className="line-clamp-4 whitespace-pre-wrap text-xs leading-5 text-muted">
                        {item.description}
                      </p>
                    )}
                    {item.url && (
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-xs text-accent hover:underline"
                      >
                        核对官方页面 <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
