import { api } from './client'
import type {
  Agent, AgentCreate, AgentUpdate,
  MarketSnapshot, MarketSummary,
  PricePrediction,
  Recommendation,
  ModelStatus, ModelVersion,
  HealthCheck,
} from './types'

// ---- Agents ----
export const agentsApi = {
  list: () => api.get<Agent[]>('/agents'),
  get: (sic: string) => api.get<Agent>(`/agents/${sic}`),
  create: (body: AgentCreate) => api.post<Agent>('/agents', body),
  update: (sic: string, body: AgentUpdate) => api.patch<Agent>(`/agents/${sic}`, body),
}

// ---- Market ----
export const marketApi = {
  latest: (agent?: string) =>
    api.get<MarketSnapshot>(`/market/latest${agent ? `?agent=${agent}` : ''}`),
  lastNHours: (hours: number, agent?: string) =>
    api.get<MarketSnapshot[]>(`/market/last/${hours}h${agent ? `?agent=${agent}` : ''}`),
  summary: (hours = 24, agent?: string) =>
    api.get<MarketSummary>(`/market/summary?hours=${hours}${agent ? `&agent=${agent}` : ''}`),
  history: (start: string, end: string, agent?: string) => {
    const q = new URLSearchParams({ start, end })
    if (agent) q.set('agent', agent)
    return api.get<{ count: number; snapshots: MarketSnapshot[] }>(`/market/history?${q}`)
  },
}

// ---- Predictions ----
export const predictionsApi = {
  latest: (agent: string) =>
    api.get<PricePrediction>(`/predictions/latest?agent=${agent}`),
}

// ---- Recommendations ----
export const recommendationsApi = {
  latest: (agent: string) =>
    api.get<Recommendation>(`/recommendations/latest?agent=${agent}`),
  generate: (sic_code: string, context_hours = 72) =>
    api.post<Recommendation>('/recommendations/generate', { sic_code, context_hours }),
}

// ---- Models ----
export const modelsApi = {
  champion: () => api.get<ModelStatus>('/models/champion'),
  versions: (stage?: string) =>
    api.get<ModelVersion[]>(`/models/versions${stage ? `?stage=${stage}` : ''}`),
}

// ---- Chat ----
export const chatApi = {
  message: (message: string, agent_sic_code: string, history: { role: string; content: string }[]) =>
    api.post<{ response: string; model_used: string }>('/chat/message', {
      message,
      agent_sic_code,
      history,
    }),
}

// ---- Health ----
export const healthApi = {
  check: () => api.get<HealthCheck>('/health'),
}

export * from './types'
