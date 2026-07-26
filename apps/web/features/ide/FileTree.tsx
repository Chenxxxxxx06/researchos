'use client';

/**
 * Explorer tree. Retokened to WS7 semantic classes and repointed at the owned
 * `@/lib/ide/store`; active-file highlight reads the store. Open flow unchanged.
 */

import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, File, FileCode2, FileText, Folder } from 'lucide-react';
import { useState } from 'react';

import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api/client';
import { getTree, type TreeNode, type TreeResponse } from '@/lib/api/workspace';
import { useIdeStore } from '@/lib/ide/store';
import { useI18n } from '@/lib/i18n';

function fileIcon(name: string) {
  if (name.endsWith('.py') || /\.(ts|tsx|js|jsx|go|rs|c|cpp|h)$/.test(name)) return FileCode2;
  if (name.endsWith('.md') || name.endsWith('.txt')) return FileText;
  return File;
}

function Node({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(true);
  const openTab = useIdeStore((s) => s.openTab);
  const active = useIdeStore((s) => s.active);

  if (node.type === 'dir') {
    return (
      <div>
        <button
          type="button"
          className="flex w-full items-center gap-1 rounded px-2 py-1 text-left text-xs text-muted hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
          style={{ paddingLeft: 8 + depth * 14 }}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? (
            <ChevronDown className="h-3 w-3 shrink-0" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-3 w-3 shrink-0" aria-hidden="true" />
          )}
          <Folder className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
          <span className="truncate">{node.name}</span>
        </button>
        {open && (node.children ?? []).map((child) => <Node key={child.path} node={child} depth={depth + 1} />)}
      </div>
    );
  }

  const Icon = fileIcon(node.name);
  const isActive = active === node.path;
  return (
    <button
      type="button"
      className={
        'flex w-full items-center gap-1.5 rounded px-2 py-1 text-left text-xs hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60 ' +
        (isActive ? 'bg-surface-2 font-medium text-text' : 'text-muted')
      }
      style={{ paddingLeft: 8 + depth * 14 }}
      onClick={() => openTab(node.path)}
    >
      <Icon className="h-3.5 w-3.5 shrink-0 text-faint" aria-hidden="true" />
      <span className="truncate">{node.name}</span>
    </button>
  );
}

export function FileTree({ projectId }: { projectId: string }) {
  const { t } = useI18n();
  const { data, isLoading, isError, refetch } = useQuery<TreeResponse, ApiError>({
    queryKey: ['workspace-tree', projectId],
    queryFn: () => getTree(projectId),
  });

  return (
    <div className="py-1">
      {isLoading && <Skeleton className="mx-3 my-2 h-16" />}
      {isError && (
        <div className="px-3 py-4 text-center">
          <p className="text-xs text-danger">{t('ide.explorerFailed')}</p>
          <button
            type="button"
            onClick={() => void refetch()}
            className="mt-1 text-xs font-medium text-info hover:underline"
          >
            {t('common.retry')}
          </button>
        </div>
      )}
      {data && data.nodes.length === 0 && (
        <EmptyState className="mx-2 mt-4 border-none" title={t('ide.explorerEmpty')} />
      )}
      {data?.nodes.map((node) => <Node key={node.path} node={node} depth={0} />)}
    </div>
  );
}
