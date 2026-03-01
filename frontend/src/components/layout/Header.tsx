import { Zap, RefreshCw } from 'lucide-react'
import { AgentSelector } from '@/components/AgentSelector'
import { ViewToggle } from '@/components/ViewToggle'
import { ModelStatusBadge } from '@/components/ModelStatusBadge'
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { cn } from '@/lib/utils'

export function Header() {
  const queryClient = useQueryClient()
  const [refreshing, setRefreshing] = useState(false)

  async function handleRefresh() {
    setRefreshing(true)
    await queryClient.invalidateQueries()
    setTimeout(() => setRefreshing(false), 1000)
  }

  return (
    <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-sm">
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Logo */}
        <div className="flex items-center gap-2 mr-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <div className="hidden sm:block">
            <p className="text-sm font-bold text-white leading-none">Agente Energía</p>
            <p className="text-xs text-zinc-500 leading-none">Colombia</p>
          </div>
        </div>

        {/* Separador */}
        <div className="h-6 w-px bg-zinc-800 hidden sm:block" />

        {/* Agent Selector */}
        <AgentSelector />

        {/* Spacer */}
        <div className="flex-1" />

        {/* Model status — solo desktop */}
        <div className="hidden lg:block">
          <ModelStatusBadge />
        </div>

        {/* View toggle */}
        <ViewToggle />

        {/* Refresh */}
        <button
          onClick={handleRefresh}
          title="Actualizar todos los datos"
          className="rounded-lg border border-zinc-800 bg-zinc-900 p-2 text-zinc-400 hover:text-zinc-200 hover:border-zinc-700 transition-all"
        >
          <RefreshCw className={cn('h-4 w-4', refreshing && 'animate-spin')} />
        </button>
      </div>
    </header>
  )
}
