import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useMarketSINHistory } from '@/hooks/useMarket'
import type { MarketSnapshot } from '@/api/types'

// Agrega datos horarios a diarios
function aggregateDaily(snapshots: MarketSnapshot[]) {
  const byDay: Record<string, number[]> = {}
  for (const s of snapshots) {
    const day = s.timestamp.slice(0, 10)
    if (!byDay[day]) byDay[day] = []
    byDay[day].push(s.spot_price_cop)
  }
  return Object.entries(byDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, prices]) => ({
      fecha: day.slice(5), // MM-DD
      precio: Math.round(prices.reduce((a, b) => a + b, 0) / prices.length),
      min: Math.round(Math.min(...prices)),
      max: Math.round(Math.max(...prices)),
    }))
}

interface TooltipProps {
  active?: boolean
  payload?: Array<{ value: number; name: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  const precio = payload.find((p) => p.name === 'Promedio')?.value
  const min = payload.find((p) => p.name === 'Min')?.value
  const max = payload.find((p) => p.name === 'Max')?.value
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-xl text-xs">
      <p className="font-medium text-zinc-300 mb-1">{label}</p>
      {precio != null && <p className="text-blue-400">Promedio: <span className="font-bold text-white">{precio.toLocaleString('es-CO')} COP/kWh</span></p>}
      {min != null && max != null && (
        <p className="text-zinc-500 mt-0.5">Rango: {min.toLocaleString('es-CO')} — {max.toLocaleString('es-CO')}</p>
      )}
    </div>
  )
}

export function PriceHistoryChart({ days = 30 }: { days?: number }) {
  const { data: snapshots, isLoading } = useMarketSINHistory(days * 24)

  if (isLoading) return <SkeletonCard rows={7} />

  if (!snapshots?.length) {
    return (
      <Card>
        <CardHeader><CardTitle>Precio Histórico — últimos {days} días</CardTitle></CardHeader>
        <CardBody className="py-10 text-center">
          <p className="text-sm text-zinc-500">Sin datos disponibles</p>
        </CardBody>
      </Card>
    )
  }

  const data = aggregateDaily(snapshots)
  const avg = Math.round(snapshots.reduce((s, x) => s + x.spot_price_cop, 0) / snapshots.length)

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Precio Spot — últimos {days} días</CardTitle>
            <p className="text-xs text-zinc-500 mt-1">
              Promedio período: <span className="text-zinc-300 font-medium">{avg.toLocaleString('es-CO')} COP/kWh</span>
            </p>
          </div>
          <div className="text-right text-xs text-zinc-600">
            {data.length} días · {snapshots.length} registros
          </div>
        </div>
      </CardHeader>
      <CardBody>
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="rangeGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.1} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
            <XAxis
              dataKey="fecha"
              tick={{ fill: '#71717a', fontSize: 10 }}
              tickLine={false}
              axisLine={{ stroke: '#27272a' }}
              interval={Math.floor(data.length / 6)}
            />
            <YAxis
              tick={{ fill: '#71717a', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}`}
              width={45}
            />
            <Tooltip content={<CustomTooltip />} />
            <ReferenceLine y={avg} stroke="#6366f1" strokeDasharray="4 2" strokeWidth={1} />
            <Area type="monotone" dataKey="max" stroke="none" fill="url(#rangeGrad)" name="Max" />
            <Area type="monotone" dataKey="min" stroke="none" fill="#09090b" name="Min" />
            <Line
              type="monotone"
              dataKey="precio"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 3, fill: '#3b82f6' }}
              name="Promedio"
            />
          </ComposedChart>
        </ResponsiveContainer>
        <div className="mt-2 flex items-center gap-4 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 bg-blue-500 inline-block" />Precio promedio diario</span>
          <span className="flex items-center gap-1.5"><span className="h-0.5 w-5 border-t border-dashed border-indigo-500 inline-block" />Promedio período</span>
          <span className="flex items-center gap-1.5"><span className="h-3 w-5 rounded bg-indigo-500/10 inline-block" />Rango min-max</span>
        </div>
      </CardBody>
    </Card>
  )
}
