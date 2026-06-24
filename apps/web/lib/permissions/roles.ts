/**
 * Front-end role helpers. These drive UI affordances only; the backend is the
 * source of truth for authorization.
 */

import type { OrgRole } from '@/lib/api/auth';

const ORG_LEVEL: Record<OrgRole, number> = { member: 0, admin: 1, owner: 2 };

export function orgRoleAtLeast(actual: OrgRole, required: OrgRole): boolean {
  return ORG_LEVEL[actual] >= ORG_LEVEL[required];
}

export function canCreateProject(role: OrgRole): boolean {
  // Any organization member may create a project.
  return orgRoleAtLeast(role, 'member');
}
