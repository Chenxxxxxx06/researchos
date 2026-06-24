/**
 * Workspace-local UI state: the currently selected organization.
 * Server state (the list of organizations) lives in TanStack Query.
 */

import { create } from 'zustand';

interface WorkspaceState {
  currentOrgId: string | null;
  setCurrentOrgId: (orgId: string | null) => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  currentOrgId: null,
  setCurrentOrgId: (orgId) => set({ currentOrgId: orgId }),
}));
