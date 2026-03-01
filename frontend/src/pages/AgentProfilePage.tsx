import { useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { User, Save, Shield, Zap } from 'lucide-react'
import { Card, CardBody, CardHeader, CardTitle } from '@/components/ui/Card'
import { Badge } from '@/components/ui/Badge'
import { useAgent } from '@/hooks/useAgents'
import { useAppStore } from '@/stores/useAppStore'
import { agentsApi } from '@/api'
import { formatRelative, riskProfileLabel } from '@/lib/utils'

const RISK_OPTIONS = [
  { value: 'conservative', label: 'Conservador', desc: 'Prioriza despacho seguro sobre margen' },
  { value: 'moderate',     label: 'Moderado',    desc: 'Balance entre ingreso y probabilidad de despacho' },
  { value: 'aggressive',   label: 'Agresivo',    desc: 'Maximiza ingreso, acepta riesgo de no despacho' },
] as const

export function AgentProfilePage() {
  const { selectedAgent } = useAppStore()
  const { data: agent, isLoading } = useAgent(selectedAgent)
  const queryClient = useQueryClient()

  const [riskProfile, setRiskProfile] = useState<string>('')
  const [capacityMw, setCapacityMw] = useState<string>('')
  const [costCopKwh, setCostCopKwh] = useState<string>('')
  const [saved, setSaved] = useState(false)

  const update = useMutation({
    mutationFn: () =>
      agentsApi.update(selectedAgent, {
        risk_profile: riskProfile || agent?.risk_profile,
        installed_capacity_mw: capacityMw ? parseFloat(capacityMw) : undefined,
        variable_cost_cop_kwh: costCopKwh ? parseFloat(costCopKwh) : undefined,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['agent', selectedAgent] })
      queryClient.invalidateQueries({ queryKey: ['agents'] })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    },
  })

  if (isLoading || !agent) {
    return (
      <div className="space-y-4">
        <div className="h-8 w-48 animate-pulse rounded-lg bg-zinc-800" />
        <div className="h-48 animate-pulse rounded-xl bg-zinc-900" />
      </div>
    )
  }

  const currentRisk = riskProfile || agent.risk_profile

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white">Perfil del Agente</h1>
        <p className="text-sm text-zinc-500 mt-0.5">
          Configuración de {agent.name} · {agent.sic_code}
        </p>
      </div>

      {/* Información básica */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <User className="h-4 w-4 text-blue-400" />
            <CardTitle>Información del Agente</CardTitle>
          </div>
        </CardHeader>
        <CardBody>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-zinc-500">Nombre</p>
              <p className="mt-1 font-medium text-white">{agent.name}</p>
            </div>
            <div>
              <p className="text-zinc-500">Código SIC</p>
              <p className="mt-1 font-mono font-medium text-white">{agent.sic_code}</p>
            </div>
            <div>
              <p className="text-zinc-500">Registrado</p>
              <p className="mt-1 text-zinc-300">{formatRelative(agent.created_at)}</p>
            </div>
            <div>
              <p className="text-zinc-500">Perfil actual</p>
              <p className="mt-1 font-medium text-white capitalize">
                {riskProfileLabel(agent.risk_profile)}
              </p>
            </div>
          </div>
        </CardBody>
      </Card>

      {/* Perfil de riesgo */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-yellow-400" />
            <CardTitle>Perfil de Riesgo</CardTitle>
          </div>
        </CardHeader>
        <CardBody>
          <div className="space-y-2">
            {RISK_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                onClick={() => setRiskProfile(opt.value)}
                className={`w-full rounded-lg border p-3 text-left transition-all ${
                  currentRisk === opt.value
                    ? 'border-blue-600 bg-blue-600/10 text-white'
                    : 'border-zinc-800 bg-zinc-800/30 text-zinc-400 hover:border-zinc-600'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{opt.label}</span>
                  {currentRisk === opt.value && (
                    <Badge variant="info">Seleccionado</Badge>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-zinc-500">{opt.desc}</p>
              </button>
            ))}
          </div>
        </CardBody>
      </Card>

      {/* Datos privados opcionales */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-emerald-400" />
              <CardTitle>Datos Privados (Opcionales)</CardTitle>
            </div>
            <Badge variant="neutral">Enriquece las recomendaciones LLM</Badge>
          </div>
        </CardHeader>
        <CardBody>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Capacidad Instalada (MW)
              </label>
              <input
                type="number"
                placeholder={agent.installed_capacity_mw?.toString() ?? 'Ej: 2400'}
                value={capacityMw}
                onChange={(e) => setCapacityMw(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-blue-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-zinc-400 uppercase tracking-wider">
                Costo Variable Declarado (COP/kWh)
              </label>
              <input
                type="number"
                placeholder={agent.variable_cost_cop_kwh?.toString() ?? 'Ej: 120.5'}
                value={costCopKwh}
                onChange={(e) => setCostCopKwh(e.target.value)}
                className="mt-1.5 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-white placeholder-zinc-600 focus:border-blue-500 focus:outline-none"
              />
              <p className="mt-1 text-xs text-zinc-600">
                Este dato es privado y solo se usa para personalizar las recomendaciones
              </p>
            </div>
          </div>

          <button
            onClick={() => update.mutate()}
            disabled={update.isPending}
            className="mt-6 flex items-center gap-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 px-5 py-2.5 text-sm font-medium text-white transition-colors"
          >
            <Save className="h-4 w-4" />
            {update.isPending ? 'Guardando…' : saved ? '¡Guardado!' : 'Guardar cambios'}
          </button>
        </CardBody>
      </Card>
    </div>
  )
}
