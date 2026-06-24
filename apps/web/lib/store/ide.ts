/** IDE local UI state: open tabs, active file, unsaved buffers, panel sizes. */

import { create } from 'zustand';

interface IdeState {
  tabs: string[];
  active: string | null;
  buffers: Record<string, string>;
  bottomHeight: number;
  rightWidth: number;

  openTab: (path: string) => void;
  closeTab: (path: string) => void;
  setActive: (path: string | null) => void;
  setBuffer: (path: string, content: string) => void;
  clearBuffer: (path: string) => void;
}

export const useIdeStore = create<IdeState>((set) => ({
  tabs: [],
  active: null,
  buffers: {},
  bottomHeight: 160,
  rightWidth: 360,

  openTab: (path) =>
    set((s) => ({
      tabs: s.tabs.includes(path) ? s.tabs : [...s.tabs, path],
      active: path,
    })),
  closeTab: (path) =>
    set((s) => {
      const tabs = s.tabs.filter((t) => t !== path);
      const buffers = { ...s.buffers };
      delete buffers[path];
      return {
        tabs,
        buffers,
        active: s.active === path ? (tabs[tabs.length - 1] ?? null) : s.active,
      };
    }),
  setActive: (path) => set({ active: path }),
  setBuffer: (path, content) => set((s) => ({ buffers: { ...s.buffers, [path]: content } })),
  clearBuffer: (path) =>
    set((s) => {
      const buffers = { ...s.buffers };
      delete buffers[path];
      return { buffers };
    }),
}));
