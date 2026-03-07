import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from 'recharts'
import { Sparkles, AlertTriangle, RefreshCw, TrendingDown, Minus, TrendingUp } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { SkeletonCard } from '@/components/ui/Skeleton'
import { useRecommendation, useGenerateRecommendation } from '@/hooks/useRecommendation'
import { formatCOP, formatRelative, riskLabel, cn } from '@/lib/utils'
import type { Recommendation } from '@/api/types'

// ---- helpers ----

function riskBadgeVariant(level: string) {
  return level === 'low' ? 'success' : level === 'medium' ? 'warning' : 'danger'
}

/**
 * Genera curva horaria 24h a partir de 3 bandas de precio.
 * Sigue el patrón colombiano: valle / rampa / día / pico / rampa bajada.
 */
function generateHourlyCurve(offPeak: number, mid: number, peak: number): number[] {
  return Array.from({ length: 24 }, (_, h) => {
    if (h < 6) return offPeak                                           // 00-05 valle
    if (h < 9) return offPeak + (mid - offPeak) * (h - 6) / 3          // 06-08 rampa mañana
    if (h < 18) return mid                                              // 09-17 día
    if (h < 21) return peak                                             // 18-20 pico
    return peak - (peak - mid) * (h - 21) / 3                          // 21-23 rampa noche
  })
}

/**
 * Dado el precio de las 3 bandas (off_peak, mid_peak, peak),
 * deriva los 3 escenarios escalando relativamente.
 *
 * Conservador: ofertas bajas para garantizar despacho (menor riesgo, menor margen)
 * Moderado:    estrategia recomendada por el LLM para este agente
 * Agresivo:    precios altos para maximizar margen (riesgo de no ser despachado)
 */
function buildScenarios(rec: Recommendation) {
  const offers = rec.hourly_offers
  if (!offers.length) return null

  // Extraer precios de las 3 franjas
  const offPeak = Math.min(...offers.map((o) => o.suggested_price_cop))
  const peakPrice = Math.max(...offers.map((o) => o.suggested_price_cop))
  const midPrice = offers.reduce((s, o) => s + o.suggested_price_cop, 0) / offers.length

  // Escenarios
  const consOffs = generateHourlyCurve(offPeak * 0.72, midPrice * 0.78, peakPrice * 0.82)
  const modOffs = generateHourlyCurve(offPeak, midPrice, peakPrice)
  const aggrOffs = generateHourlyCurve(offPeak * 1.22, midPrice * 1.28, peakPrice * 1.35)

  return Array.from({ length: 24 }, (_, h) => ({
    hora: `${String(h).padStart(2, '0')}h`,
    h,
    Conservador: Math.round(consOffs[h]),
    Moderado: Math.round(modOffs[h]),
    Agresivo: Math.round(aggrOffs[h]),
    isPeak: h >= 18 && h < 21,
  }))
}

// ---- Tooltip personalizado ----
interface TooltipProps {
  active?: boolean
  payload?: Array<{ name: string; value: number; color: string }>
  label?: string
}

function OfferTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-900 p-3 shadow-xl text-xs min-w-[160px]">
      <p className="text-zinc-400 mb-2">{label}</p>
      {payload.map((p) => (
        <div key={p.name} className="flex justify-between gap-3 mb-0.5">
          <span style={{ color: p.color }}>{p.name}</span>
          <span className="font-bold text-white">{p.value.toLocaleString('es-CO')} COP</span>
        </div>
      ))}
    </div>
  )
}

// ---- Gráfico 24h con 3 escenarios ----
function OfferChart({ rec }: { rec: Recommendation }) {
  const [activeProfile, setActiveProfile] = useState<string | null>(null)
  const data = buildScenarios(rec)
  if (!data) return null

  const agentRisk = rec.risk_level === 'low' ? 'Conservador' : rec.risk_level === 'medium' ? 'Moderado' : 'Agresivo'

  const PROFILES = [
    { key: 'Conservador', color: '#22c55e', label: 'Conservador', icon: TrendingDown },
    { key: 'Moderado',   color: '#f59e0b', label: 'Moderado',    icon: Minus },
    { key: 'Agresivo',  color: '#ef4444', label: 'Agresivo',    icon: TrendingUp },
  ]

  return (
    <div className="mt-4 space-y-4">
      {/* Selector de perfil visible */}
      <div className="flex gap-2 flex-wrap">
        {PROFILES.map(({ key, color, label, icon: Icon }) => {
          const isRecommended = key === agentRisk
          const isActive = activeProfile === null || activeProfile === key
          return (
            <button
              key={key}
              onClick={() => setActiveProfile(activeProfile === key ? null : key)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-all',
                isActive
                  ? 'border-opacity-70 bg-zinc-800'
                  : 'border-zinc-800 bg-zinc-900 opacity-40',
              )}
              style={{ borderColor: color }}
            >
              <Icon className="h-3 w-3" style={{ color }} />
              <span style={{ color }}>{label}</span>
              {isRecommended && (
                <span className="rounded-full bg-zinc-700 px-1.5 py-0.5 text-zinc-300">recomendado</span>
              )}
            </button>
          )
        })}
      </div>

      <p className="text-xs text-zinc-600">
        Curvas basadas en el análisis LLM · Escenarios derivados del perfil {agentRisk.toLowerCase()}
      </p>

      <ResponsiveContainer width="100%" height={220}>
        <LineChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
          <XAxis
            dataKey="hora"
            tick={{ fill: '#71717a', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#27272a' }}
            interval={2}
          />
          <YAxis
            tick={{ fill: '#71717a', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            width={45}
          />
          <Tooltip content={<OfferTooltip />} />
          {/* Zona pico */}
          <ReferenceLine x="18h" stroke="#f97316" strokeDasharray="3 2" strokeWidth={1}
            label={{ value: 'Pico', fill: '#f97316', fontSize: 9, position: 'top' }} />
          <ReferenceLine x="21h" stroke="#f97316" strokeDasharray="3 2" strokeWidth={1} />

          {PROFILES.map(({ key, color }) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={color}
              strokeWidth={key === agentRisk ? 2.5 : 1.5}
              dot={false}
              activeDot={{ r: 3 }}
              opacity={activeProfile === null || activeProfile === key ? 1 : 0.15}
              strokeDasharray={key === 'Conservador' ? '5 3' : key === 'Agresivo' ? '2 2' : undefined}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>

      {/* Tabla resumen de precios promedio */}
      <div className="grid grid-cols-3 gap-2">
        {PROFILES.map(({ key, color, label }) => {
          const vals = data.map((d) => d[key as keyof typeof d] as number)
          const avg = Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
          const peakAvg = Math.round(data.filter((d) => d.isPeak).reduce((s, d) => s + (d[key as keyof typeof d] as number), 0) / 3)
          const isRecommended = key === agentRisk
          return (
            <div key={key} className={cn(
              'rounded-lg border p-2.5 text-center',
              isRecommended ? 'border-zinc-600 bg-zinc-800/60' : 'border-zinc-800',
            )}>
              <p className="text-xs font-medium mb-1" style={{ color }}>{label}</p>
              <p className="text-base font-bold text-white">{avg.toLocaleString('es-CO')}</p>
              <p className="text-xs text-zinc-500">prom. 24h</p>
              <p className="text-xs text-orange-400 mt-0.5">Pico: {peakAvg.toLocaleString('es-CO')}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ---- Card principal ----
export function RecommendationCard() {
  const { data: rec, isLoading, error } = useRecommendation()
  const generate = useGenerateRecommendation()

  if (isLoading) return <SkeletonCard rows={8} />

  if (error || !rec) {
    return (
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-400" />
            <CardTitle>Recomendación de Oferta</CardTitle>
          </div>
        </CardHeader>
        <CardBody className="py-10 text-center">
          <AlertTriangle className="h-8 w-8 text-zinc-600 mx-auto mb-3" />
          <p className="text-sm text-zinc-400">Sin recomendación disponible para este agente</p>
          <button
            onClick={() => generate.mutate(72)}
            disabled={generate.isPending}
            className="mt-4 flex items-center gap-2 mx-auto rounded-lg bg-purple-600 hover:bg-purple-500 disabled:opacity-50 px-4 py-2 text-sm font-medium text-white transition-colors"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', generate.isPending && 'animate-spin')} />
            {generate.isPending ? 'Generando…' : 'Generar recomendación'}
          </button>
        </CardBody>
      </Card>
    )
  }

  const agentRisk = rec.risk_level === 'low' ? 'Conservador' : rec.risk_level === 'medium' ? 'Moderado' : 'Agresivo'
  const data = buildScenarios(rec)
  const recVals = data?.map((d) => d[agentRisk as keyof typeof d] as number) ?? []
  const recAvg = recVals.length ? Math.round(recVals.reduce((a, b) => a + b, 0) / recVals.length) : rec.avg_suggested_price

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-purple-400" />
            <CardTitle>Recomendación de Oferta — próximas 24h</CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={riskBadgeVariant(rec.risk_level)} dot>
              {riskLabel(rec.risk_level)}
            </Badge>
            <button
              onClick={() => generate.mutate(72)}
              disabled={generate.isPending}
              title="Regenerar recomendación"
              className="rounded-lg p-1.5 text-zinc-600 hover:text-zinc-300 hover:bg-zinc-800 transition-colors"
            >
              <RefreshCw className={cn('h-3.5 w-3.5', generate.isPending && 'animate-spin')} />
            </button>
          </div>
        </div>

        {/* KPI precio promedio para el perfil recomendado */}
        <div className="mt-3 flex items-end justify-between">
          <div>
            <p className="text-xs text-zinc-500">Oferta sugerida promedio 24h · perfil {agentRisk.toLowerCase()}</p>
            <div className="flex items-baseline gap-2 mt-1">
              <span className="text-3xl font-bold text-white">
                {formatCOP(recAvg, 0)}
              </span>
              <span className="text-sm text-zinc-500">/kWh</span>
            </div>
          </div>
          <p className="text-xs text-zinc-600 text-right">
            {rec.llm_model_used}<br />{formatRelative(rec.generated_at)}
          </p>
        </div>
      </CardHeader>

      <CardBody>
        {/* Análisis LLM */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-start gap-2">
            <Sparkles className="h-3.5 w-3.5 text-purple-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-xs font-medium text-zinc-500 mb-1.5">Análisis del agente</p>
              <p className="text-sm text-zinc-300 leading-relaxed">{rec.narrative}</p>
            </div>
          </div>
        </div>

        {/* Factores clave */}
        <div className="mt-4 flex flex-wrap gap-1.5">
          {rec.key_factors.map((f, i) => (
            <Badge key={i} variant="neutral">{f}</Badge>
          ))}
        </div>

        {/* Gráfico 24h con 3 perfiles */}
        <OfferChart rec={rec} />
      </CardBody>
    </Card>
  )
}
