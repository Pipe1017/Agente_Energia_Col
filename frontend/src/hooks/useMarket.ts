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
