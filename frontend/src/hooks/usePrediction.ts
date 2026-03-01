import { useQuery } from '@tanstack/react-query'
import { predictionsApi } from '@/api'
import { useAppStore } from '@/stores/useAppStore'

export function usePrediction() {
  const agent = useAppStore((s) => s.selectedAgent)
  return useQuery({
    queryKey: ['prediction', 'latest', agent],
    queryFn: () => predictionsApi.latest(agent),
    refetchInterval: 60 * 60 * 1000, // 1 hora
    staleTime: 55 * 60 * 1000,
    retry: 1,
  })
}
