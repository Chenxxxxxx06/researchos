'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { getTree, type TreeNode, type TreeResponse } from '@/lib/api/workspace';
import { ApiError } from '@/lib/api/client';
import { useIdeStore } from '@/lib/store/ide';
import { Skeleton } from '@/components/ui/skeleton';

function Node({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(true);
  const openTab = useIdeStore((s) => s.openTab);
  const active = useIdeStore((s) => s.active);

  if (node.type === 'dir') {
    return (
      <div>
        <button className="flex w-full items-center gap-1 rounded px-2 py-1 text-left text-xs text-neutral-600 hover:bg-neutral-100" style={{ paddingLeft: 8 + depth * 14 }} onClick={() => setOpen(!open)}>
          <span className="text-[10px]">{open ? '▾' : '▸'}</span>📁 {node.name}
        </button>
        {open && (node.children ?? []).map((child) => <Node key={child.path} node={child} depth={depth + 1} />)}
      </div>
    );
  }
  const icon = node.name.endsWith('.py') ? '🐍' : node.name.endsWith('.md') ? '📝' : '📄';
  return (
    <button className={`flex w-full items-center gap-1 rounded px-2 py-1 text-left text-xs hover:bg-neutral-100 ${active === node.path ? 'bg-neutral-200 font-medium text-neutral-900' : 'text-neutral-700'}`}
      style={{ paddingLeft: 8 + depth * 14 }} onClick={() => openTab(node.path)}>
      <span className="text-[10px]">{icon}</span> {node.name}
    </button>
  );
}

export function FileTree({ projectId }: { projectId: string }) {
  const { data, isLoading, isError } = useQuery<TreeResponse, ApiError>({
    queryKey: ['workspace-tree', projectId], queryFn: () => getTree(projectId),
  });

  return (
    <div>
      <h3 className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-neutral-400">Explorer</h3>
      {isLoading && <Skeleton className="mx-3 h-16" />}
      {isError && <p className="px-3 text-xs text-red-600">Failed.</p>}
      {data && data.nodes.length === 0 && <p className="px-3 text-xs text-neutral-400">Empty.</p>}
      {data?.nodes.map((node) => <Node key={node.path} node={node} depth={0} />)}
    </div>
  );
}
