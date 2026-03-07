import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { recommendationsApi } from '@/api'
import { useAppStore } from '@/stores/useAppStore'

export function useRecommendation() {
  const agent = useAppStore((s) => s.selectedAgent)
  return useQuery({
    queryKey: ['recommendation', 'latest', agent],
    queryFn: () => recommendationsApi.latest(agent),
    refetchInterval: 60 * 60 * 1000,
    staleTime: 55 * 60 * 1000,
    retry: 1,
  })
}

export function useGenerateRecommendation() {
  const agent = useAppStore((s) => s.selectedAgent)
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (contextHours?: number) =>
      recommendationsApi.generate(agent, contextHours ?? 72),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendation', 'latest', agent] })
    },
  })
}
