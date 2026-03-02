import { useState } from 'react'
import { Sparkles, ChevronDown, ChevronUp, AlertTriangle, RefreshCw } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useRecommendation, useGenerateRecommendation } from '@/hooks/useRecommendation'
import { formatCOP, formatRelative, riskLabel, cn } from '@/lib/utils'
import type { HourlyOffer } from '@/api/types'

function RiskBadgeVariant(level: string) {
  return level === 'low' ? 'success' : level === 'medium' ? 'warning' : 'danger'
}

function HourlyOffersTable({ offers }: { offers: HourlyOffer[] }) {
  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-zinc-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-800/50">
            <th className="px-3 py-2 text-left font-medium text-zinc-400">Hora</th>
            <th className="px-3 py-2 text-right font-medium text-zinc-400">Precio Oferta</th>
            <th className="px-3 py-2 text-left font-medium text-zinc-400 hidden sm:table-cell">Justificación</th>
          </tr>
        </thead>
        <tbody>
          {offers.map((o, i) => {
            const hour = new Date(o.hour).getHours()
            return (
              <tr
                key={i}
                className={cn(
                  'border-b border-zinc-800/50 last:border-0',
                  o.is_peak_hour && 'bg-orange-500/5',
                )}
              >
                <td className="px-3 py-2 font-mono text-zinc-300">
                  {String(hour).padStart(2, '0')}:00
                  {o.is_peak_hour && (
                    <span className="ml-1.5 rounded-sm bg-orange-500/20 px-1 text-orange-400">pico</span>
                  )}
                </td>
                <td className="px-3 py-2 text-right font-semibold text-white">
                  {formatCOP(o.suggested_price_cop, 0)}
                </td>
                <td className="px-3 py-2 text-zinc-500 hidden sm:table-cell max-w-xs truncate">
                  {o.reasoning}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

export function RecommendationCard() {
  const { data: rec, isLoading, error } = useRecommendation()
  const generate = useGenerateRecommendation()
  const [showOffers, setShowOffers] = useState(false)

  if (isLoading) return <SkeletonCard rows={7} />

  if (error || !rec) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-400" />
            <CardTitle>Recomendación de Oferta</CardTitle>
          </div>
        </CardHeader>
        <CardBody className="py-8 text-center">
          <AlertTriangle className="h-8 w-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-sm text-zinc-400">Sin recomendación disponible</p>
          <button
            onClick={() => generate.mutate(72)}
            disabled={generate.isPending}
            className="mt-4 flex items-center gap-2 mx-auto rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 px-4 py-2 text-sm font-medium text-white transition-colors"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', generate.isPending && 'animate-spin')} />
            {generate.isPending ? 'Generando…' : 'Generar ahora'}
          </button>
        </CardBody>
      </Card>
    )
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-400" />
            <CardTitle>Recomendación de Oferta</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={RiskBadgeVariant(rec.risk_level)} dot>
              Riesgo {riskLabel(rec.risk_level)}
            </Badge>
            <button
              onClick={() => generate.mutate(72)}
              disabled={generate.isPending}
              title="Regenerar recomendación (consume tokens LLM)"
              className="rounded-lg p-1.5 text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', generate.isPending && 'animate-spin')} />
            </button>
          </div>
        </div>

        {/* Precio promedio recomendado — KPI principal */}
        <div className="mt-3">
          <p className="text-xs text-zinc-500">Precio de oferta sugerido (promedio 24h)</p>
          <div className="flex items-baseline gap-2 mt-1">
            <span className="text-3xl font-bold text-white">
              {formatCOP(rec.avg_suggested_price, 0)}
            </span>
            <span className="text-sm text-zinc-500">/kWh</span>
          </div>
        </div>
      </CardHeader>

      <CardBody>
        {/* Narrative */}
        <div className="rounded-lg bg-zinc-800/50 border border-zinc-800 p-4">
          <p className="text-sm text-zinc-300 leading-relaxed">{rec.narrative}</p>
        </div>

        {/* Factores clave */}
        <div className="mt-4">
          <p className="text-xs font-medium text-zinc-500 uppercase tracking-wider mb-2">
            Factores clave
          </p>
          <div className="flex flex-wrap gap-1.5">
            {rec.key_factors.map((f, i) => (
              <Badge key={i} variant="neutral">{f}</Badge>
            ))}
          </div>
        </div>

        {/* Estrategia horaria */}
        <button
          onClick={() => setShowOffers((v) => !v)}
          className="mt-4 flex w-full items-center justify-between rounded-lg border border-zinc-800 px-3 py-2.5 text-sm text-zinc-400 hover:bg-zinc-800/50 transition-colors"
        >
          <span className="font-medium">Ver oferta hora a hora ({rec.hourly_offers.length}h)</span>
          {showOffers
            ? <ChevronUp className="h-4 w-4" />
            : <ChevronDown className="h-4 w-4" />
          }
        </button>

        {showOffers && <HourlyOffersTable offers={rec.hourly_offers} />}

        <p className="mt-3 text-right text-xs text-zinc-600">
          vía {rec.llm_model_used} · {formatRelative(rec.generated_at)}
        </p>
      </CardBody>
    </Card>
  )
}
