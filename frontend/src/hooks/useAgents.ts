import { useQuery } from '@tanstack/react-query'
import { agentsApi, modelsApi } from '@/api'

export function useAgents() {
  return useQuery({
    queryKey: ['agents'],
    queryFn: agentsApi.list,
    staleTime: 10 * 60 * 1000,
  })
}

export function useAgent(sic: string) {
  return useQuery({
    queryKey: ['agent', sic],
    queryFn: () => agentsApi.get(sic),
    enabled: !!sic,
    staleTime: 10 * 60 * 1000,
  })
}

export function useModelStatus() {
  return useQuery({
    queryKey: ['models', 'champion'],
    queryFn: modelsApi.champion,
    refetchInterval: 30 * 60 * 1000,
    staleTime: 25 * 60 * 1000,
  })
}
