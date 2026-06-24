'use client';

import { useEffect } from 'react';

import type { OrganizationSummary } from '@/lib/api/auth';
import { useWorkspaceStore } from '@/lib/store/workspace';

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

  return (
    <select
      aria-label="Organization"
      className="h-8 rounded-md border border-neutral-300 bg-white px-2 text-sm"
      value={currentOrgId ?? organizations[0]!.id}
      onChange={(e) => setCurrentOrgId(e.target.value)}
    >
      {organizations.map((org) => (
        <option key={org.id} value={org.id}>
          {org.name}
        </option>
      ))}
    </select>
  );
}
