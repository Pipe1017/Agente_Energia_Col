import { useAppStore } from '@/stores/useAppStore'
import { MarketCard } from '@/components/MarketCard'
import { PredictionChart } from '@/components/charts/PredictionChart'
import { RecommendationCard } from '@/components/RecommendationCard'
import { useRecommendation } from '@/hooks/useRecommendation'
import { usePrediction } from '@/hooks/usePrediction'
import { useMarketLatest } from '@/hooks/useMarket'
import { formatCOP, formatRelative, riskLabel, hydrologyColor, cn } from '@/lib/utils'
import { Sparkles, TrendingUp, Droplets, Activity } from 'lucide-react'
import { Card, CardBody } from '@/components/ui/Card'

// ------------------------------------------------------------------
// Vista Ejecutiva — KPIs grandes, mínimo ruido
// ------------------------------------------------------------------

function ExecutiveKPI({
  icon,
  label,
  value,
  sub,
  valueClass,
}: {
  icon: React.ReactNode
  label: string
  value: string
  sub?: string
  valueClass?: string
}) {
  return (
    <Card>
      <CardBody className="py-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-zinc-500 uppercase tracking-wider">{label}</p>
            <p className={cn('mt-2 text-3xl font-bold', valueClass ?? 'text-white')}>{value}</p>
            {sub && <p className="mt-1 text-xs text-zinc-500">{sub}</p>}
          </div>
          <div className="rounded-lg bg-zinc-800 p-2.5">{icon}</div>
        </div>
      </CardBody>
    </Card>
  )
}

function ExecutiveView() {
  const { data: market } = useMarketLatest()
  const { data: prediction } = usePrediction()
  const { data: rec } = useRecommendation()

  return (
    <div className="space-y-6 animate-fade-in">
      {/* KPI Row */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <ExecutiveKPI
          icon={<Activity className="h-5 w-5 text-blue-400" />}
          label="Precio Spot Actual"
          value={market ? formatCOP(market.spot_price_cop, 0) : '—'}
          sub="COP / kWh"
        />
        <ExecutiveKPI
          icon={<Sparkles className="h-5 w-5 text-purple-400" />}
          label="Oferta Recomendada"
          value={rec ? formatCOP(rec.avg_suggested_price, 0) : '—'}
          sub={rec ? `Riesgo ${riskLabel(rec.risk_level)}` : 'Pendiente'}
          valueClass={rec ? 'text-purple-300' : 'text-zinc-500'}
        />
        <ExecutiveKPI
          icon={<TrendingUp className="h-5 w-5 text-emerald-400" />}
          label="Predicción Precio 24h"
          value={prediction ? formatCOP(prediction.avg_predicted_price, 0) : '—'}
          sub={prediction ? `Pico: ${formatCOP(prediction.peak_avg_price, 0)}` : undefined}
        />
        <ExecutiveKPI
          icon={<Droplets className="h-5 w-5 text-blue-400" />}
          label="Estado Hidrológico"
          value={market ? `${market.hydrology_pct.toFixed(0)}%` : '—'}
          sub={market?.hydrology_status.toUpperCase()}
          valueClass={market ? hydrologyColor(market.hydrology_status) : 'text-zinc-500'}
        />
      </div>

      {/* Recommendation summary */}
      {rec && (
        <Card glass>
          <CardBody className="py-4">
            <div className="flex items-start gap-3">
              <Sparkles className="h-5 w-5 text-purple-400 shrink-0 mt-0.5" />
              <div>
                <p className="text-sm font-medium text-zinc-200">{rec.summary}</p>
                <p className="mt-1 text-xs text-zinc-600">
                  {formatRelative(rec.generated_at)} · vía {rec.llm_model_used}
                </p>
              </div>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Chart */}
      <PredictionChart />
    </div>
  )
}

// ------------------------------------------------------------------
// Vista Técnica — detalle completo
// ------------------------------------------------------------------

function TechnicalView() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Columna izquierda: mercado */}
        <div className="space-y-6">
          <MarketCard />
        </div>

        {/* Columna central (2/3): predicción */}
        <div className="lg:col-span-2 space-y-6">
          <PredictionChart />
          <RecommendationCard />
        </div>
      </div>
    </div>
  )
}

// ------------------------------------------------------------------
// Dashboard page
// ------------------------------------------------------------------

export function DashboardPage() {
  const { viewMode, selectedAgent } = useAppStore()

  return (
    <div>
      {/* Page header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-white">Dashboard</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Mercado eléctrico colombiano · Agente <span className="text-zinc-300">{selectedAgent}</span>
        </p>
      </div>

      {viewMode === 'executive' ? <ExecutiveView /> : <TechnicalView />}
    </div>
  )
}
