import { ChevronDown, Zap } from 'lucide-react'
import { useAgents } from '@/hooks/useAgents'
import { useAppStore } from '@/stores/useAppStore'
import { cn } from '@/lib/utils'
import { useState, useRef, useEffect } from 'react'

const RISK_COLORS = {
  conservative: 'text-emerald-400',
  moderate: 'text-yellow-400',
  aggressive: 'text-red-400',
}

export function AgentSelector() {
  const { data: agents, isLoading } = useAgents()
  const { selectedAgent, setSelectedAgent } = useAppStore()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const current = agents?.find((a) => a.sic_code === selectedAgent)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
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
        <div className="absolute right-0 top-full z-50 mt-1 w-64 animate-fade-in rounded-xl border border-zinc-700 bg-zinc-900 shadow-2xl">
          <div className="p-1">
            <p className="px-3 py-2 text-xs font-medium text-zinc-500 uppercase tracking-wider">
              Agentes disponibles
            </p>
            {agents?.map((agent) => (
              <button
                key={agent.sic_code}
                onClick={() => { setSelectedAgent(agent.sic_code); setOpen(false) }}
                className={cn(
                  'flex w-full items-center justify-between rounded-lg px-3 py-2.5 text-left',
                  'hover:bg-zinc-800 transition-colors duration-100',
                  agent.sic_code === selectedAgent && 'bg-blue-600/20 text-blue-300',
                )}
              >
                <div>
                  <p className="text-sm font-medium text-white">{agent.name}</p>
                  <p className="text-xs text-zinc-500">{agent.sic_code}</p>
                </div>
                <div className="text-right">
                  <p className={cn(
                    'text-xs font-medium capitalize',
                    RISK_COLORS[agent.risk_profile],
                  )}>
                    {agent.risk_profile === 'conservative' ? 'Conservador' :
                     agent.risk_profile === 'moderate' ? 'Moderado' : 'Agresivo'}
                  </p>
                  {agent.installed_capacity_mw && (
                    <p className="text-xs text-zinc-600">{agent.installed_capacity_mw} MW</p>
                  )}
                </div>
              </button>
            ))}

            <div className="border-t border-zinc-800 mt-1 pt-1">
              <button
                onClick={() => { window.location.href = '/profile' }}
                className="flex w-full items-center px-3 py-2 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
              >
                + Configurar perfil del agente
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
