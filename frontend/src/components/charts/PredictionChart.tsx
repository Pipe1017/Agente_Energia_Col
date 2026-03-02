import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ReferenceLine, ResponsiveContainer,
} from 'recharts'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { Badge } from '@/components/ui/Badge'
import { usePrediction } from '@/hooks/usePrediction'
import { formatCOP, formatHour, formatRelative } from '@/lib/utils'

interface TooltipProps {
  active?: boolean
  payload?: Array<{ value: number; name: string; color: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  const predicted = payload.find((p) => p.name === 'Predicción')?.value ?? 0
  const lower = payload.find((p) => p.name === 'Límite inferior')?.value ?? 0
  const upper = payload.find((p) => p.name === 'Límite superior')?.value ?? 0

  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-xl text-xs">
      <p className="font-medium text-zinc-300 mb-2">{label}</p>
      <p className="text-blue-400">Predicción: <span className="font-bold text-white">{formatCOP(predicted, 1)}</span></p>
      <p className="text-zinc-500 mt-1">
        Intervalo: {formatCOP(lower, 0)} — {formatCOP(upper, 0)}
      </p>
    </div>
  )
}

export function PredictionChart() {
  const { data: prediction, isLoading, error } = usePrediction()

  if (isLoading) return <SkeletonCard rows={8} />

  if (error || !prediction) {
    return (
      <Card>
        <CardHeader><CardTitle>Predicción de Precio 24h</CardTitle></CardHeader>
        <CardBody className="py-12 text-center">
          <p className="text-sm text-zinc-500">Sin predicción disponible</p>
          <p className="text-xs text-zinc-700 mt-1">
            El modelo champion genera predicciones cada hora
          </p>
        </CardBody>
      </Card>
    )
  }

  const chartData = prediction.hourly_predictions.map((h) => ({
    hora: formatHour(h.target_hour),
    'Predicción': h.predicted_cop,
    'Límite superior': h.upper_bound_cop,
    'Límite inferior': h.lower_bound_cop,
    isPeak: h.is_peak_hour,
  }))

  const peakHours = prediction.hourly_predictions.filter((h) => h.is_peak_hour)
  const peakAvg = peakHours.length
    ? peakHours.reduce((s, h) => s + h.predicted_cop, 0) / peakHours.length
    : 0

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle>Predicción de Precio 24h</CardTitle>
            <div className="mt-2 flex items-baseline gap-3">
              <div>
                <span className="text-2xl font-bold text-white">
                  {formatCOP(prediction.avg_predicted_price, 0)}
                </span>
                <span className="text-sm text-zinc-500 ml-1">promedio</span>
              </div>
              <div className="text-sm text-orange-400">
                Pico 18-21h: <span className="font-semibold">{formatCOP(peakAvg, 0)}</span>
              </div>
            </div>
          </div>
          <div className="flex flex-col items-end gap-1.5">
            <Badge variant="info">
              Confianza {(prediction.overall_confidence * 100).toFixed(0)}%
            </Badge>
            <p className="text-xs text-zinc-600">
              Generado {formatRelative(prediction.generated_at)}
            </p>
          </div>
        </div>
      </CardHeader>

      <CardBody>
        <ResponsiveContainer width="100%" height={260}>
          <AreaChart data={chartData} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="predGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="intervalGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.15} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="hora"
              tick={{ fill: '#71717a', fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: '#27272a' }}
              interval={3}
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`}
              width={40}
            />
            <Tooltip content={<CustomTooltip />} />
            {/* Zona de horas pico */}
            <ReferenceLine
              x="18:00"
              stroke="#f97316"
              strokeDasharray="4 2"
              strokeWidth={1}
              label={{ value: 'Pico', fill: '#f97316', fontSize: 10, position: 'top' }}
            />
            {/* Intervalo de confianza */}
            <Area
              type="monotone"
              dataKey="Límite superior"
              stroke="none"
              fill="url(#intervalGradient)"
              fillOpacity={1}
            />
            <Area
              type="monotone"
              dataKey="Límite inferior"
              stroke="none"
              fill="#09090b"
              fillOpacity={1}
            />
            {/* Predicción central */}
            <Area
              type="monotone"
              dataKey="Predicción"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#predGradient)"
              dot={false}
              activeDot={{ r: 4, fill: '#3b82f6' }}
            />
          </AreaChart>
        </ResponsiveContainer>

        {/* Leyenda */}
        <div className="mt-3 flex items-center gap-4 text-xs text-zinc-500">
          <div className="flex items-center gap-1.5">
            <div className="h-0.5 w-6 bg-blue-500" />
            <span>Predicción central</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-6 rounded bg-indigo-500/20" />
            <span>Intervalo 90% confianza</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-0.5 w-4 border-t border-dashed border-orange-400" />
            <span>Inicio hora pico</span>
          </div>
        </div>
      </CardBody>
    </Card>
  )
}
