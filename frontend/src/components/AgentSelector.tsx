import { ChevronDown, Zap, Check } from 'lucide-react'
import { useAgents } from '@/hooks/useAgents'
import { useAppStore } from '@/stores/useAppStore'
import { agentsApi } from '@/api'
import { cn } from '@/lib/utils'
import { useState, useRef, useEffect } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'

const RISK_COLORS = {
  conservative: 'text-emerald-400',
  moderate: 'text-yellow-400',
  aggressive: 'text-red-400',
}
const RISK_LABELS = {
  conservative: 'Conservador',
  moderate: 'Moderado',
  aggressive: 'Agresivo',
}
const RISK_OPTIONS = ['conservative', 'moderate', 'aggressive'] as const

export function AgentSelector() {
  const { data: agents, isLoading } = useAgents()
  const { selectedAgent, setSelectedAgent } = useAppStore()
  const [open, setOpen] = useState(false)
  const [editingAgent, setEditingAgent] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  const queryClient = useQueryClient()

  const current = agents?.find((a) => a.sic_code === selectedAgent)

  const updateRisk = useMutation({
    mutationFn: ({ sic, risk }: { sic: string; risk: string }) =>
      agentsApi.update(sic, { risk_profile: risk as 'conservative' | 'moderate' | 'aggressive' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setEditingAgent(null)
    },
  })

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
        setEditingAgent(null)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 py-2">
        <div className="h-4 w-32 animate-pulse rounded bg-zinc-700" />
      </div>
    )
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className={cn(
          'flex items-center gap-2 rounded-lg border border-zinc-700 bg-zinc-800/80 px-3 py-2',
          'hover:border-zinc-500 hover:bg-zinc-800 transition-all duration-150',
          'text-sm font-medium text-white',
          open && 'border-zinc-500 bg-zinc-800',
        )}
      >
        <Zap className="h-4 w-4 text-yellow-400" />
        <span>{current?.name ?? selectedAgent}</span>
        <span className="text-xs text-zinc-500">{selectedAgent}</span>
        <ChevronDown className={cn('h-4 w-4 text-zinc-400 transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-72 animate-fade-in rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
          <div className="p-1">
            <p className="px-3 py-2 text-xs font-medium text-zinc-500 uppercase tracking-wider">
              Agentes disponibles
            </p>

            {agents?.map((agent) => (
              <div key={agent.sic_code}>
                <button
                  onClick={() => {
                    setSelectedAgent(agent.sic_code)
                    setEditingAgent(null)
                    setOpen(false)
                  }}
                  className={cn(
                    'flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left',
                    'hover:bg-zinc-800 transition-colors duration-100',
                    agent.sic_code === selectedAgent && 'bg-blue-600/20',
                  )}
                >
                  <div>
                    <p className={cn('text-sm font-medium', agent.sic_code === selectedAgent ? 'text-blue-300' : 'text-white')}>
                      {agent.name}
                    </p>
                    <p className="text-xs text-zinc-500">{agent.sic_code}</p>
                  </div>
                  <div
                    className="text-right"
                    onClick={(e) => {
                      e.stopPropagation()
                      setEditingAgent(editingAgent === agent.sic_code ? null : agent.sic_code)
                    }}
                  >
                    <p className={cn(
                      'text-xs font-medium capitalize hover:underline cursor-pointer',
                      RISK_COLORS[agent.risk_profile],
                    )}>
                      {RISK_LABELS[agent.risk_profile]}
                    </p>
                    {agent.installed_capacity_mw && (
                      <p className="text-xs text-zinc-600">{agent.installed_capacity_mw} MW</p>
                    )}
                  </div>
                </button>

                {/* Inline risk editor */}
                {editingAgent === agent.sic_code && (
                  <div className="mx-2 mb-1 rounded-lg border border-zinc-700 bg-zinc-800 p-2">
                    <p className="text-xs text-zinc-500 mb-1.5 px-1">Cambiar perfil de riesgo:</p>
                    <div className="flex gap-1">
                      {RISK_OPTIONS.map((r) => (
                        <button
                          key={r}
                          onClick={() => updateRisk.mutate({ sic: agent.sic_code, risk: r })}
                          disabled={updateRisk.isPending}
                          className={cn(
                            'flex-1 flex items-center justify-center gap-1 rounded-md py-1.5 text-xs font-medium transition-colors',
                            agent.risk_profile === r
                              ? 'bg-zinc-600 text-white'
                              : 'text-zinc-400 hover:bg-zinc-700 hover:text-white',
                          )}
                        >
                          {agent.risk_profile === r && <Check className="h-3 w-3" />}
                          {RISK_LABELS[r]}
                        </button>
                      ))}
                    </div>
                    {updateRisk.isPending && (
                      <p className="text-xs text-zinc-500 text-center mt-1.5">Guardando…</p>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
