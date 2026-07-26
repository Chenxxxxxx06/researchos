'use client';

import { useEffect } from 'react';
import { Building2 } from 'lucide-react';

import type { OrganizationSummary } from '@/lib/api/auth';
import { useWorkspaceStore } from '@/lib/store/workspace';
import { Badge } from '@/components/ui/badge';
import { Dropdown, DropdownRadioItem } from '@/components/ui/dropdown';

export function OrgSwitcher({ organizations }: { organizations: OrganizationSummary[] }) {
  const currentOrgId = useWorkspaceStore((s) => s.currentOrgId);
  const setCurrentOrgId = useWorkspaceStore((s) => s.setCurrentOrgId);

  // Default to the first organization once loaded.
  useEffect(() => {
    if (!currentOrgId && organizations.length > 0) {
      setCurrentOrgId(organizations[0]!.id);
    }
  }, [currentOrgId, organizations, setCurrentOrgId]);

  if (organizations.length === 0) return null;

  const current =
    organizations.find((org) => org.id === currentOrgId) ?? organizations[0]!;

  return (
    <Dropdown
      panelClassName="min-w-56"
      trigger={
        <button
          type="button"
          aria-label="Organization"
          className="flex h-8 max-w-44 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 text-sm text-text hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus/60"
        >
          <Building2 className="h-3.5 w-3.5 shrink-0 text-muted" aria-hidden="true" />
          <span className="truncate">{current.name}</span>
        </button>
      }
    >
      {organizations.map((org) => (
        <DropdownRadioItem
          key={org.id}
          checked={org.id === current.id}
          onSelect={() => setCurrentOrgId(org.id)}
        >
          <span className="flex items-center gap-2">
            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-surface-2 text-[10px] font-semibold uppercase text-muted">
              {org.name.charAt(0)}
            </span>
            <span className="truncate">{org.name}</span>
            <Badge variant="outline" size="sm">
              {org.role}
            </Badge>
          </span>
        </DropdownRadioItem>
      ))}
    </Dropdown>
  );
}
