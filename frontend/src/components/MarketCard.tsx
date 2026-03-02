import { Droplets, TrendingUp, TrendingDown, Minus } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useMarketLatest, useMarketSummary } from '@/hooks/useMarket'
import { formatCOP, formatMWh, formatPct, formatRelative, hydrologyColor, hydrologyBg, cn } from '@/lib/utils'

function TrendIcon({ pct }: { pct: number }) {
  if (Math.abs(pct) < 0.5) return <Minus className="h-4 w-4 text-zinc-400" />
  return pct > 0
    ? <TrendingUp className="h-4 w-4 text-red-400" />
    : <TrendingDown className="h-4 w-4 text-emerald-400" />
}

function MetricRow({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-zinc-800/50 last:border-0">
      <span className="text-sm text-zinc-400">{label}</span>
      <div className="text-right">
        <span className="text-sm font-medium text-white">{value}</span>
        {sub && <p className="text-xs text-zinc-600">{sub}</p>}
      </div>
    </div>
  )
}

export function MarketCard() {
  const { data: market, isLoading, error } = useMarketLatest()
  const { data: summary } = useMarketSummary(24)

  if (isLoading) return <SkeletonCard rows={6} />
  if (error || !market) {
    return (
      <Card className="border-red-900/30 bg-red-950/20">
        <CardBody className="py-8 text-center">
          <p className="text-sm text-red-400">Sin datos de mercado</p>
          <p className="text-xs text-zinc-600 mt-1">Verificar conexión con XM API</p>
        </CardBody>
      </Card>
    )
  }

  const trend24h = summary
    ? ((market.spot_price_cop - summary.avg_price_cop) / summary.avg_price_cop) * 100
    : 0

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between">
          <div>
            <CardTitle>Mercado Spot</CardTitle>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold text-white">
                {formatCOP(market.spot_price_cop, 1)}
              </span>
              <span className="text-sm text-zinc-500">/kWh</span>
            </div>
            <div className="mt-1 flex items-center gap-1.5">
              <TrendIcon pct={trend24h} />
              <span className={cn(
                'text-xs',
                Math.abs(trend24h) < 0.5 ? 'text-zinc-400' :
                trend24h > 0 ? 'text-red-400' : 'text-emerald-400'
              )}>
                {trend24h > 0 ? '+' : ''}{trend24h.toFixed(1)}% vs prom. 24h
              </span>
            </div>
          </div>
          <Badge
            variant={
              market.hydrology_status === 'crítica' ? 'danger' :
              market.hydrology_status === 'baja' ? 'warning' :
              market.hydrology_status === 'alta' ? 'success' : 'info'
            }
            dot
          >
            {market.hydrology_status.toUpperCase()}
          </Badge>
        </div>
      </CardHeader>

      <CardBody>
        {/* Hidrología highlight */}
        <div className={cn(
          'mb-4 rounded-lg border p-3',
          hydrologyBg(market.hydrology_status),
        )}>
          <div className="flex items-center gap-2 mb-2">
            <Droplets className={cn('h-4 w-4', hydrologyColor(market.hydrology_status))} />
            <span className="text-xs font-medium text-zinc-300">Estado Hidrológico</span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-zinc-500">Aportes</p>
              <p className={cn('text-lg font-bold', hydrologyColor(market.hydrology_status))}>
                {formatPct(market.hydrology_pct)}
              </p>
              <p className="text-xs text-zinc-600">del histórico</p>
            </div>
            <div>
              <p className="text-xs text-zinc-500">Embalses</p>
              <p className="text-lg font-bold text-white">
                {formatPct(market.reservoir_level_pct)}
              </p>
              <p className="text-xs text-zinc-600">capacidad</p>
            </div>
          </div>
        </div>

        {/* Otras métricas */}
        <div>
          <MetricRow
            label="Demanda SIN"
            value={formatMWh(market.demand_mwh)}
          />
          <MetricRow
            label="Despacho Térmico"
            value={formatPct(market.thermal_dispatch_pct)}
          />
          {summary && (
            <>
              <MetricRow
                label="Precio prom. 24h"
                value={formatCOP(summary.avg_price_cop, 1)}
                sub={`min: ${formatCOP(summary.min_price_cop, 0)} — max: ${formatCOP(summary.max_price_cop, 0)}`}
              />
            </>
          )}
        </div>

        <p className="mt-3 text-right text-xs text-zinc-600">
          Actualizado {formatRelative(market.timestamp)}
        </p>
      </CardBody>
    </Card>
  )
}
