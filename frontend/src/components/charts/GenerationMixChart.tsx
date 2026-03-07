import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useMarketSINHistory } from '@/hooks/useMarket'
import type { MarketSnapshot } from '@/api/types'

function aggregateDaily(snapshots: MarketSnapshot[]) {
  const byDay: Record<string, { hidro: number[]; termica: number[]; solar: number[]; eolica: number[] }> = {}
  for (const s of snapshots) {
    const day = s.timestamp.slice(0, 10)
    if (!byDay[day]) byDay[day] = { hidro: [], termica: [], solar: [], eolica: [] }
    if (s.gen_hidraulica_gwh != null) byDay[day].hidro.push(s.gen_hidraulica_gwh)
    if (s.gen_termica_gwh != null) byDay[day].termica.push(s.gen_termica_gwh)
    if (s.gen_solar_gwh != null) byDay[day].solar.push(s.gen_solar_gwh)
    if (s.gen_eolica_gwh != null) byDay[day].eolica.push(s.gen_eolica_gwh)
  }
  return Object.entries(byDay)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([day, g]) => {
      const avg = (arr: number[]) => arr.length ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0
      return {
        fecha: day.slice(5),
        Hidráulica: avg(g.hidro),
        Térmica: avg(g.termica),
        Solar: avg(g.solar),
        Eólica: avg(g.eolica),
      }
    })
}

interface TooltipProps {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}

function CustomTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  const total = payload.reduce((s, p) => s + (p.value || 0), 0)
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-xl text-xs min-w-[160px]">
      <p className="font-medium text-zinc-300 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-4 mb-0.5">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="text-white font-medium">{p.value} GWh</span>
        </div>
      ))}
      <div className="border-t border-zinc-700 mt-2 pt-1.5 flex justify-between">
        <span className="text-zinc-400">Total</span>
        <span className="text-white font-bold">{total} GWh</span>
      </div>
    </div>
  )
}

export function GenerationMixChart({ days = 30 }: { days?: number }) {
  const { data: snapshots, isLoading } = useMarketSINHistory(days * 24)

  if (isLoading) return <SkeletonCard rows={7} />

  const hasGen = snapshots?.some((s) => s.gen_hidraulica_gwh != null)

  if (!snapshots?.length || !hasGen) {
    return (
      <Card>
        <CardHeader><CardTitle>Mix de Generación — últimos {days} días</CardTitle></CardHeader>
        <CardBody className="py-10 text-center">
          <p className="text-sm text-zinc-500">Sin datos de generación disponibles</p>
        </CardBody>
      </Card>
    )
  }

  const data = aggregateDaily(snapshots)
  const lastDay = data[data.length - 1]
  const totalLast = lastDay
    ? lastDay.Hidráulica + lastDay.Térmica + lastDay.Solar + lastDay.Eólica
    : 0
  const hidroPct = totalLast > 0 ? Math.round((lastDay.Hidráulica / totalLast) * 100) : 0

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Mix de Generación — últimos {days} días</CardTitle>
            <p className="text-xs text-zinc-500 mt-1">
              Último día: <span className="text-blue-400 font-medium">{hidroPct}% hidráulica</span>
              {totalLast > 0 && <span className="text-zinc-600 ml-2">· {totalLast} GWh total</span>}
            </p>
          </div>
          <span className="text-xs text-zinc-600">GWh/día · promedio diario</span>
        </div>
      </CardHeader>
      <CardBody>
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="hidroGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.7} />
                <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.2} />
              </linearGradient>
              <linearGradient id="termGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#f97316" stopOpacity={0.7} />
                <stop offset="95%" stopColor="#f97316" stopOpacity={0.2} />
              </linearGradient>
              <linearGradient id="solarGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#eab308" stopOpacity={0.7} />
                <stop offset="95%" stopColor="#eab308" stopOpacity={0.2} />
              </linearGradient>
              <linearGradient id="eolicaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#22c55e" stopOpacity={0.7} />
                <stop offset="95%" stopColor="#22c55e" stopOpacity={0.2} />
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
              width={40}
            />
            <Tooltip content={<CustomTooltip />} />
            <Legend
              wrapperStyle={{ fontSize: 11, paddingTop: 8 }}
              formatter={(value) => <span style={{ color: '#a1a1aa' }}>{value}</span>}
            />
            <Area type="monotone" dataKey="Hidráulica" stackId="1" stroke="#3b82f6" fill="url(#hidroGrad)" strokeWidth={1.5} />
            <Area type="monotone" dataKey="Térmica" stackId="1" stroke="#f97316" fill="url(#termGrad)" strokeWidth={1.5} />
            <Area type="monotone" dataKey="Solar" stackId="1" stroke="#eab308" fill="url(#solarGrad)" strokeWidth={1.5} />
            <Area type="monotone" dataKey="Eólica" stackId="1" stroke="#22c55e" fill="url(#eolicaGrad)" strokeWidth={1.5} />
          </AreaChart>
        </ResponsiveContainer>
      </CardBody>
    </Card>
  )
}
