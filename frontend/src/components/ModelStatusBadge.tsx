import { Brain, CheckCircle, AlertCircle } from 'lucide-react'
import { useModelStatus } from '@/hooks/useAgents'
import { Badge } from '@/components/ui/Badge'
import { formatRelative } from '@/lib/utils'

export function ModelStatusBadge() {
  const { data: status } = useModelStatus()

  if (!status) return null

  if (!status.has_champion) {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-yellow-900/30 bg-yellow-950/20 px-3 py-2">
        <AlertCircle className="h-4 w-4 text-yellow-400" />
        <span className="text-xs text-yellow-400">Sin modelo champion</span>
      </div>
    )
  }

  const { champion } = status

  return (
    <div className="flex items-center gap-2 rounded-lg border border-zinc-800 bg-zinc-900/50 px-3 py-2">
      <Brain className="h-4 w-4 text-emerald-400" />
      <div className="flex items-center gap-2 text-xs">
        <span className="text-zinc-400">Modelo:</span>
        <span className="font-medium text-white">{champion!.name}@{champion!.version}</span>
        <Badge variant="success" dot>production</Badge>
        {champion!.metrics.rmse && (
          <span className="text-zinc-600 hidden sm:inline">
            RMSE {champion!.metrics.rmse.toFixed(1)} COP
          </span>
        )}
        {champion!.promoted_at && (
          <span className="text-zinc-700 hidden md:inline">
            · {formatRelative(champion!.promoted_at)}
          </span>
        )}
      </div>
    </div>
  )
}
