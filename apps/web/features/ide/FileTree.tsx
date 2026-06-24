'use client';

import { useQuery } from '@tanstack/react-query';

import { getTree, type TreeNode, type TreeResponse } from '@/lib/api/workspace';
import { ApiError } from '@/lib/api/client';
import { useIdeStore } from '@/lib/store/ide';
import { Skeleton } from '@/components/ui/skeleton';

function Node({ node, depth }: { node: TreeNode; depth: number }) {
  const openTab = useIdeStore((s) => s.openTab);
  if (node.type === 'dir') {
    return (
      <div>
        <div className="px-2 py-0.5 text-xs font-semibold text-neutral-500" style={{ paddingLeft: depth * 12 + 8 }}>
          {node.name}/
        </div>
        {(node.children ?? []).map((child) => (
          <Node key={child.path} node={child} depth={depth + 1} />
        ))}
      </div>
    );
  }
  return (
    <button
      className="block w-full truncate px-2 py-0.5 text-left text-xs text-neutral-800 hover:bg-neutral-100"
      style={{ paddingLeft: depth * 12 + 8 }}
      onClick={() => openTab(node.path)}
    >
      {node.name}
    </button>
  );
}

export function FileTree({ projectId }: { projectId: string }) {
  const { data, isLoading, isError } = useQuery<TreeResponse, ApiError>({
    queryKey: ['workspace-tree', projectId],
    queryFn: () => getTree(projectId),
  });

  return (
    <div>
      <h3 className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Explorer
      </h3>
      {isLoading && <Skeleton className="mx-2 h-24" />}
      {isError && <p className="px-2 text-xs text-red-600">Failed to load tree.</p>}
      {data && data.nodes.length === 0 && (
        <p className="px-2 text-xs text-neutral-400">Empty workspace.</p>
      )}
      {data?.nodes.map((node) => (
        <Node key={node.path} node={node} depth={0} />
      ))}
    </div>
  );
}
