import { useQuery } from '@tanstack/react-query'
import { Brain, Award, Clock, BarChart2 } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useModelStatus } from '@/hooks/useAgents'
import { modelsApi } from '@/api'
import { formatRelative, formatDateTime } from '@/lib/utils'
import type { ModelVersion } from '@/api/types'

function StageBadge({ stage }: { stage: string }) {
  const variants = {
    production: 'success',
    staging:    'warning',
    dev:        'info',
    archived:   'neutral',
  } as const
  return (
    <Badge variant={variants[stage as keyof typeof variants] ?? 'neutral'} dot>
      {stage}
    </Badge>
  )
}

function MetricCell({ label, value }: { label: string; value: number | null }) {
  if (value == null) return <td className="px-4 py-3 text-zinc-600">—</td>
  return (
    <td className="px-4 py-3 font-mono text-sm text-zinc-300">
      {value.toFixed(2)}
    </td>
  )
}

function VersionRow({ model }: { model: ModelVersion }) {
  return (
    <tr className="border-b border-zinc-800/50 last:border-0 hover:bg-zinc-800/20 transition-colors">
      <td className="px-4 py-3">
        <div>
          <p className="text-sm font-medium text-white">{model.name}@{model.version}</p>
          <p className="text-xs text-zinc-600">{model.algorithm}</p>
        </div>
      </td>
      <td className="px-4 py-3"><StageBadge stage={model.stage} /></td>
      <MetricCell label="RMSE" value={model.metrics.rmse} />
      <MetricCell label="MAPE" value={model.metrics.mape} />
      <MetricCell label="R²"   value={model.metrics.r2}   />
      <td className="px-4 py-3 text-xs text-zinc-500">
        {model.trained_on_days}d
      </td>
      <td className="px-4 py-3 text-xs text-zinc-500">
        {formatDateTime(model.trained_at)}
      </td>
    </tr>
  )
}

export function ModelsPage() {
  const { data: status } = useModelStatus()
  const { data: versions } = useQuery({
    queryKey: ['models', 'versions'],
    queryFn: modelsApi.versions,
    staleTime: 10 * 60 * 1000,
  })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Modelos ML</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Estado del ciclo de vida de los modelos XGBoost
        </p>
      </div>

      {/* Champion card */}
      {status?.champion && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Award className="h-5 w-5 text-yellow-400" />
              <CardTitle>Modelo Champion</CardTitle>
              <Badge variant="success" dot>production</Badge>
            </div>
          </CardHeader>
          <CardBody>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-6">
              <div>
                <p className="text-xs text-zinc-500 mb-1">Versión</p>
                <p className="text-lg font-bold text-white">
                  {status.champion.name}@{status.champion.version}
                </p>
                <p className="text-xs text-zinc-600">{status.champion.algorithm}</p>
              </div>
              {[
                { label: 'RMSE', value: status.champion.metrics.rmse, unit: 'COP' },
                { label: 'MAPE', value: status.champion.metrics.mape, unit: '%' },
                { label: 'R²',   value: status.champion.metrics.r2,   unit: '' },
              ].map(({ label, value, unit }) => (
                <div key={label}>
                  <p className="text-xs text-zinc-500 mb-1">{label}</p>
                  <p className="text-lg font-bold text-white">
                    {value != null ? `${value.toFixed(2)} ${unit}` : '—'}
                  </p>
                </div>
              ))}
            </div>

            <div className="mt-4 flex items-center gap-4 text-xs text-zinc-500 border-t border-zinc-800 pt-4">
              <div className="flex items-center gap-1.5">
                <Brain className="h-3.5 w-3.5" />
                <span>Entrenado con {status.champion.trained_on_days} días de datos</span>
              </div>
              {status.champion.promoted_at && (
                <div className="flex items-center gap-1.5">
                  <Clock className="h-3.5 w-3.5" />
                  <span>Promovido {formatRelative(status.champion.promoted_at)}</span>
                </div>
              )}
              <div>Total versiones: <span className="text-zinc-300">{status.total_versions}</span></div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* All versions table */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <BarChart2 className="h-4 w-4 text-blue-400" />
            <CardTitle>Historial de Versiones</CardTitle>
          </div>
        </CardHeader>
        <CardBody className="px-0 pb-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 bg-zinc-800/30">
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Modelo</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Stage</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">RMSE</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">MAPE%</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">R²</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Datos</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase tracking-wider">Entrenado</th>
                </tr>
              </thead>
              <tbody>
                {versions?.map((v) => <VersionRow key={v.id} model={v} />) ?? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-zinc-600">
                      Sin versiones registradas
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  )
}
