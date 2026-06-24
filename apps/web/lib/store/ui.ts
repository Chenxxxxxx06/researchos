/**
 * UI / local workspace state (Zustand).
 *
 * Per the Phase 0 decisions, server state lives in TanStack Query and only
 * ephemeral UI state lives here. This placeholder store models the global
 * navigation rail collapse state; feature stores are added per phase.
 */

import { create } from 'zustand';

interface UiState {
  sidebarCollapsed: boolean;
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
}

export const useUiStore = create<UiState>((set) => ({
  sidebarCollapsed: false,
  toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
  setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),
}));
