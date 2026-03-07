import { useQuery } from '@tanstack/react-query'
import { marketApi } from '@/api'
import { useAppStore } from '@/stores/useAppStore'

const REFETCH_INTERVAL = 5 * 60 * 1000 // 5 min

export function useMarketLatest() {
  const agent = useAppStore((s) => s.selectedAgent)
  return useQuery({
    queryKey: ['market', 'latest', agent],
    queryFn: () => marketApi.latest(agent),
    refetchInterval: REFETCH_INTERVAL,
    staleTime: 4 * 60 * 1000,
  })
}

export function useMarketHistory(hours = 24) {
  const agent = useAppStore((s) => s.selectedAgent)
  return useQuery({
    queryKey: ['market', 'history', hours, agent],
    queryFn: () => marketApi.lastNHours(hours, agent),
    refetchInterval: REFETCH_INTERVAL,
    staleTime: 4 * 60 * 1000,
  })
}

export function useMarketSummary(hours = 24) {
  const agent = useAppStore((s) => s.selectedAgent)
  return useQuery({
    queryKey: ['market', 'summary', hours, agent],
    queryFn: () => marketApi.summary(hours, agent),
    refetchInterval: REFETCH_INTERVAL,
    staleTime: 4 * 60 * 1000,
  })
}

/** Historial SIN (sin agente) — para gráficas de precio, generación e hidrología.
 *  Los datos del mercado eléctrico colombiano son sistema-wide, no por agente. */
export function useMarketSINHistory(hours: number) {
  return useQuery({
    queryKey: ['market', 'sin-history', hours],
    queryFn: () => marketApi.lastNHours(hours),   // sin agente → datos SIN
    staleTime: 10 * 60 * 1000,
    refetchInterval: false,
  })
}

/** Historial completo por rango de fechas (datos crudos de BD). */
export function useMarketDateRange(start: string, end: string) {
  return useQuery({
    queryKey: ['market', 'daterange', start, end],
    queryFn: async () => {
      const res = await marketApi.history(start, end)
      return res.snapshots
    },
    staleTime: 10 * 60 * 1000,
    refetchInterval: false,
  })
}
