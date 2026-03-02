import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export type ViewMode = 'executive' | 'technical'

interface AppStore {
  // Agent Selector
  selectedAgent: string
  setSelectedAgent: (sic: string) => void

  // View mode toggle
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
  toggleViewMode: () => void

  // Sidebar
  sidebarOpen: boolean
  setSidebarOpen: (open: boolean) => void
}

export const useAppStore = create<AppStore>()(
  persist(
    (set, get) => ({
      selectedAgent: 'EPMC',
      setSelectedAgent: (sic) => set({ selectedAgent: sic }),

      viewMode: 'executive',
      setViewMode: (mode) => set({ viewMode: mode }),
      toggleViewMode: () =>
        set({ viewMode: get().viewMode === 'executive' ? 'technical' : 'executive' }),

      sidebarOpen: true,
      setSidebarOpen: (open) => set({ sidebarOpen: open }),
    }),
    {
      name: 'agente-energia-prefs',
      partialize: (state) => ({
        selectedAgent: state.selectedAgent,
        viewMode: state.viewMode,
      }),
    },
  ),
)
