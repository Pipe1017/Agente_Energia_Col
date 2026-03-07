import { useAppStore } from '@/stores/useAppStore'
import { PriceHistoryChart } from '@/components/charts/PriceHistoryChart'
import { GenerationMixChart } from '@/components/charts/GenerationMixChart'
import { HydrologyChart } from '@/components/charts/HydrologyChart'
import { RecommendationCard } from '@/components/RecommendationCard'
import { useMarketLatest } from '@/hooks/useMarket'
import { useRecommendation } from '@/hooks/useRecommendation'
import { useAgents } from '@/hooks/useAgents'
import { Card, CardBody } from '@/components/ui/Card'
import { Activity, Droplets, Zap, Sparkles } from 'lucide-react'

// ---- KPI simple ----
function KPI({
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
      <CardBody className="py-4">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-xs text-zinc-500 uppercase tracking-wider">{label}</p>
            <p className={`mt-1.5 text-2xl font-bold ${valueClass ?? 'text-white'}`}>{value}</p>
            {sub && <p className="mt-0.5 text-xs text-zinc-500">{sub}</p>}
          </div>
          <div className="rounded-lg bg-zinc-800 p-2">{icon}</div>
        </div>
      </CardBody>
    </Card>
  )
}

// ---- Vista Ejecutiva ----
function ExecutiveView() {
  const { data: market } = useMarketLatest()
  const { data: rec } = useRecommendation()

  const hydroColor =
    market?.hydrology_status === 'alta' ? 'text-emerald-400'
    : market?.hydrology_status === 'normal' ? 'text-blue-400'
    : market?.hydrology_status === 'baja' ? 'text-yellow-400'
    : 'text-red-400'

  return (
    <div className="space-y-6 animate-fade-in">
      {/* KPIs */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPI
          icon={<Activity className="h-4 w-4 text-blue-400" />}
          label="Precio Spot"
          value={market ? `${market.spot_price_cop.toFixed(0)} COP` : '—'}
          sub={market ? `Actualizado: ${market.timestamp.slice(0, 10)}` : 'Cargando...'}
        />
        <KPI
          icon={<Zap className="h-4 w-4 text-orange-400" />}
          label="Precio Escasez"
          value={market?.precio_escasez_cop ? `${market.precio_escasez_cop.toFixed(0)} COP` : '—'}
          sub="COP / kWh"
        />
        <KPI
          icon={<Droplets className="h-4 w-4 text-blue-400" />}
          label="Nivel Embalses"
          value={market ? `${market.reservoir_level_pct.toFixed(1)}%` : '—'}
          sub={market ? `Hidrología: ${market.hydrology_status}` : undefined}
          valueClass={market ? hydroColor : 'text-zinc-500'}
        />
        <KPI
          icon={<Sparkles className="h-4 w-4 text-purple-400" />}
          label="Oferta Sugerida"
          value={rec ? `${rec.avg_suggested_price.toFixed(0)} COP` : '—'}
          sub={rec ? `Riesgo: ${rec.risk_level}` : 'Sin recomendación'}
          valueClass={rec ? 'text-purple-300' : 'text-zinc-500'}
        />
      </div>

      {/* Recomendación LLM (si existe) */}
      {rec && (
        <Card glass>
          <CardBody className="py-4">
            <div className="flex items-start gap-3">
              <Sparkles className="h-4 w-4 text-purple-400 shrink-0 mt-0.5" />
              <p className="text-sm text-zinc-200">{rec.summary}</p>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Gráficas históricas */}
      <PriceHistoryChart days={30} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <GenerationMixChart days={30} />
        <HydrologyChart days={30} />
      </div>

      {/* Recomendación completa */}
      <RecommendationCard />
    </div>
  )
}

// ---- Vista Técnica ----
function TechnicalView() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PriceHistoryChart days={60} />
        <HydrologyChart days={60} />
      </div>
      <GenerationMixChart days={60} />
      <RecommendationCard />
    </div>
  )
}

const RISK_COLORS: Record<string, string> = {
  conservative: 'text-emerald-400 bg-emerald-400/10',
  moderate: 'text-yellow-400 bg-yellow-400/10',
  aggressive: 'text-red-400 bg-red-400/10',
}
const RISK_LABELS: Record<string, string> = {
  conservative: 'Conservador',
  moderate: 'Moderado',
  aggressive: 'Agresivo',
}

// ---- Dashboard page ----
export function DashboardPage() {
  const { viewMode, selectedAgent } = useAppStore()
  const { data: agents } = useAgents()
  const agent = agents?.find((a) => a.sic_code === selectedAgent)

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">
            {agent?.name ?? selectedAgent}
          </h1>
          <div className="flex items-center flex-wrap gap-2 mt-1.5">
            <span className="text-sm text-zinc-500">{selectedAgent}</span>
            {agent?.risk_profile && (
              <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${RISK_COLORS[agent.risk_profile]}`}>
                {RISK_LABELS[agent.risk_profile]}
              </span>
            )}
            {agent?.installed_capacity_mw && (
              <span className="text-xs text-zinc-600">{agent.installed_capacity_mw} MW</span>
            )}
            {agent?.resources?.map((r) => (
              <span key={r} className="rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400 capitalize">{r}</span>
            ))}
          </div>
        </div>
      </div>
      {viewMode === 'executive' ? <ExecutiveView /> : <TechnicalView />}
    </div>
  )
}
