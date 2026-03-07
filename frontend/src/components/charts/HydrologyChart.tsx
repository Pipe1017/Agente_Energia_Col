import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend,
} from 'recharts'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useMarketSINHistory } from '@/hooks/useMarket'
import type { MarketSnapshot } from '@/api/types'

function aggregateDaily(snapshots: MarketSnapshot[]) {
  const byDay: Record<string, { reservoir: number[]; hydro: number[] }> = {}
  for (const s of snapshots) {
    const day = s.timestamp.slice(0, 10)
    if (!byDay[day]) byDay[day] = { reservoir: [], hydro: [] }
    byDay[day].reservoir.push(s.reservoir_level_pct)
    byDay[day].hydro.push(s.hydrology_pct)
  }
  return Object.entries(byDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, g]) => ({
      fecha: day.slice(5),
      'Embalses (%)': parseFloat(
        (g.reservoir.reduce((a, b) => a + b, 0) / g.reservoir.length).toFixed(1)
      ),
      'Aportes (% hist.)': parseFloat(
        (g.hydro.reduce((a, b) => a + b, 0) / g.hydro.length).toFixed(1)
      ),
    }))
}

interface TooltipProps {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-xl text-xs">
      <p className="font-medium text-zinc-300 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4 mb-0.5">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-white font-medium">{p.value}%</span>
        </div>
      ))}
    </div>
  )
}

export function HydrologyChart({ days = 30 }: { days?: number }) {
  const { data: snapshots, isLoading } = useMarketSINHistory(days * 24)

  if (isLoading) return <SkeletonCard rows={7} />

  if (!snapshots?.length) {
    return (
      <Card>
        <CardHeader><CardTitle>Hidrología y Embalses — últimos {days} días</CardTitle></CardHeader>
        <CardBody className="py-10 text-center">
          <p className="text-sm text-zinc-500">Sin datos disponibles</p>
        </CardBody>
      </Card>
    )
  }

  const data = aggregateDaily(snapshots)
  const latest = data[data.length - 1]

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Hidrología y Embalses — últimos {days} días</CardTitle>
            {latest && (
              <p className="text-xs text-zinc-500 mt-1">
                Último: embalses <span className="text-blue-400 font-medium">{latest['Embalses (%)'].toFixed(1)}%</span>
                {' · '}aportes <span className="text-emerald-400 font-medium">{latest['Aportes (% hist.)'].toFixed(1)}%</span> del histórico
              </p>
            )}
          </div>
        </div>
      </CardHeader>
      <CardBody>
        <ResponsiveContainer width="100%" height={240}>
          <ComposedChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="reservoirGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
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
              yAxisId="reservoir"
              tick={{ fill: '#71717a', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
              domain={[0, 100]}
              width={42}
            />
            <YAxis
              yAxisId="hydro"
              orientation="right"
              tick={{ fill: '#71717a', fontSize: 10 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v) => `${v}%`}
              width={42}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
              formatter={(value) => <span style={{ color: '#a1a1aa' }}>{value}</span>}
            />
            {/* Zona crítica embalses: < 30% */}
            <ReferenceLine yAxisId="reservoir" y={30} stroke="#ef4444" strokeDasharray="4 2" strokeWidth={1}
              label={{ value: 'Crítico', fill: '#ef4444', fontSize: 9, position: 'insideTopRight' }} />
            {/* Zona crítica aportes: < 60% */}
            <ReferenceLine yAxisId="hydro" y={60} stroke="#f97316" strokeDasharray="4 2" strokeWidth={1} />
            <Area
              yAxisId="reservoir"
              type="monotone"
              dataKey="Embalses (%)"
              stroke="#3b82f6"
              strokeWidth={2}
              fill="url(#reservoirGrad)"
              dot={false}
            />
            <Line
              yAxisId="hydro"
              type="monotone"
              dataKey="Aportes (% hist.)"
              stroke="#10b981"
              strokeWidth={1.5}
              dot={false}
              strokeDasharray="5 3"
            />
          </ComposedChart>
        </ResponsiveContainer>
        <div className="mt-2 flex items-center gap-5 text-xs text-zinc-500">
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-5 bg-red-500 inline-block border-t border-dashed border-red-500" />
            Nivel crítico embalses (30%)
          </span>
          <span className="flex items-center gap-1.5">
            <span className="h-0.5 w-5 bg-orange-500 inline-block border-t border-dashed border-orange-500" />
            Aportes críticos (60% hist.)
          </span>
        </div>
      </CardBody>
    </Card>
  )
}
