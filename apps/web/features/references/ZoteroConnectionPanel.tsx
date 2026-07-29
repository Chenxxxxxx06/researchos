'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { CheckCircle2, CloudDownload, PlugZap } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { ApiError } from '@/lib/api/client';
import {
  getZoteroConnection,
  saveZoteroConnection,
  syncZoteroLibrary,
  testZoteroConnection,
  type ZoteroConnection,
} from '@/lib/api/zotero';
import { cn } from '@/lib/utils';

export function ZoteroConnectionPanel({ projectId }: { projectId: string }) {
  const qc = useQueryClient();
  const connection = useQuery({
    queryKey: ['zotero-connection', projectId],
    queryFn: () => getZoteroConnection(projectId),
  });
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    library_type: 'user' as 'user' | 'group',
    library_id: '',
    api_key: '',
    enabled: true,
  });

  useEffect(() => {
    if (!connection.data) return;
    setForm({
      library_type: connection.data.library_type,
      library_id: connection.data.library_id,
      api_key: '',
      enabled: connection.data.enabled,
    });
  }, [connection.data]);

  const save = useMutation({
    mutationFn: () => saveZoteroConnection(projectId, form),
    onSuccess: () => {
      setEditing(false);
      void qc.invalidateQueries({ queryKey: ['zotero-connection', projectId] });
    },
  });
  const test = useMutation({ mutationFn: () => testZoteroConnection(projectId) });
  const sync = useMutation({
    mutationFn: () => syncZoteroLibrary(projectId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['zotero-connection', projectId] });
      void qc.invalidateQueries({ queryKey: ['papers', projectId] });
      void qc.invalidateQueries({ queryKey: ['feed', projectId] });
    },
  });

  const configured = Boolean(connection.data);
  const showForm = !configured || editing;
  const apiError =
    (test.error instanceof ApiError && test.error.message) ||
    (sync.error instanceof ApiError && sync.error.message) ||
    null;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <PlugZap className="h-4 w-4" aria-hidden="true" /> Zotero
          </CardTitle>
          {configured && !editing && (
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}>编辑</Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {showForm ? (
          <form
            className="space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              save.mutate();
            }}
          >
            <div>
              <Label>文库类型</Label>
              <select
                className="h-10 w-full rounded-md border border-border-strong bg-surface px-3 text-sm text-text"
                value={form.library_type}
                onChange={(event) =>
                  setForm({ ...form, library_type: event.target.value as 'user' | 'group' })
                }
              >
                <option value="user">个人文库</option>
                <option value="group">群组文库</option>
              </select>
            </div>
            <div>
              <Label>Library ID</Label>
              <Input
                value={form.library_id}
                onChange={(event) => setForm({ ...form, library_id: event.target.value })}
                placeholder="例如 12345678"
                required
              />
              <p className="mt-1 text-[11px] text-faint">不是用户名，可在 Zotero API Keys 页面查看。</p>
            </div>
            <div>
              <Label>API Key</Label>
              <Input
                type="password"
                value={form.api_key}
                onChange={(event) => setForm({ ...form, api_key: event.target.value })}
                placeholder={configured ? '留空则保持原 Key' : '需要文库读取权限'}
                required={!configured}
              />
            </div>
            {save.error instanceof ApiError && (
              <p className="rounded bg-danger-bg px-3 py-2 text-xs text-danger">
                {save.error.message}
              </p>
            )}
            <div className="flex gap-2">
              <Button type="submit" size="sm" loading={save.isPending}>保存连接</Button>
              {configured && (
                <Button type="button" size="sm" variant="secondary" onClick={() => setEditing(false)}>
                  取消
                </Button>
              )}
            </div>
          </form>
        ) : (
          <ConnectionSummary connection={connection.data as ZoteroConnection} />
        )}

        {configured && !editing && (
          <>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" onClick={() => test.mutate()} loading={test.isPending}>
                <CheckCircle2 className="mr-1.5 h-3.5 w-3.5" /> 检测权限
              </Button>
              <Button size="sm" onClick={() => sync.mutate()} loading={sync.isPending}>
                <CloudDownload className="mr-1.5 h-3.5 w-3.5" /> 同步文库
              </Button>
            </div>
            {test.data && (
              <ResultBox ok={test.data.ok}>{test.data.message} · {test.data.latency_ms} ms</ResultBox>
            )}
            {sync.data && (
              <ResultBox ok>
                已同步：新增 {sync.data.created}，更新 {sync.data.updated}，关联 {sync.data.linked}，跳过 {sync.data.skipped}
              </ResultBox>
            )}
            {apiError && <ResultBox ok={false}>{apiError}</ResultBox>}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ConnectionSummary({ connection }: { connection: ZoteroConnection }) {
  return (
    <div className="space-y-1 text-xs text-muted">
      <p className="font-medium text-text">
        {connection.library_type === 'user' ? '个人文库' : '群组文库'} · {connection.library_id}
      </p>
      <p>Key：{connection.api_key_masked}</p>
      <p>最近同步：{connection.last_synced_at ? new Date(connection.last_synced_at).toLocaleString() : '尚未同步'}</p>
      {connection.last_error && <p className="text-danger">{connection.last_error}</p>}
    </div>
  );
}

function ResultBox({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <div className={cn(
      'rounded-md border px-3 py-2 text-xs',
      ok ? 'border-success/30 bg-success-bg text-success' : 'border-danger/30 bg-danger-bg text-danger',
    )}>
      {children}
    </div>
  );
}
