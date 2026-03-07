// ============================================================
// API Response Types — reflect backend Pydantic schemas
// ============================================================

export interface Agent {
  id: string
  name: string
  sic_code: string
  risk_profile: 'conservative' | 'moderate' | 'aggressive'
  installed_capacity_mw: number | null
  variable_cost_cop_kwh: number | null
  resources: string[]
  created_at: string
  is_configured: boolean
}

export interface AgentCreate {
  name: string
  sic_code: string
  risk_profile?: 'conservative' | 'moderate' | 'aggressive'
  installed_capacity_mw?: number
  variable_cost_cop_kwh?: number
  resources?: string[]
}

export interface AgentUpdate {
  risk_profile?: 'conservative' | 'moderate' | 'aggressive'
  installed_capacity_mw?: number
  variable_cost_cop_kwh?: number
  resources?: string[]
}

// ---- Market ----

export interface MarketSnapshot {
  timestamp: string
  spot_price_cop: number
  demand_mwh: number
  hydrology_pct: number
  reservoir_level_pct: number
  thermal_dispatch_pct: number
  agent_sic_code: string | null
  precio_escasez_cop: number | null
  gen_hidraulica_gwh: number | null
  gen_termica_gwh: number | null
  gen_solar_gwh: number | null
  gen_eolica_gwh: number | null
  hydrology_status: 'crítica' | 'baja' | 'normal' | 'alta'
  is_hydrology_critical: boolean
  is_reservoir_low: boolean
}

export interface MarketSummary {
  period_hours: number
  avg_price_cop: number
  min_price_cop: number
  max_price_cop: number
  avg_demand_mwh: number
  avg_hydrology_pct: number
  avg_reservoir_pct: number
  current_hydrology_status: string
  latest_timestamp: string
}

// ---- Predictions ----

export interface HourlyPrice {
  target_hour: string
  predicted_cop: number
  lower_bound_cop: number
  upper_bound_cop: number
  confidence: number
  is_peak_hour: boolean
  spread_cop: number
}

export interface PricePrediction {
  id: string
  agent_sic_code: string
  generated_at: string
  model_version_id: string
  horizon_hours: number
  overall_confidence: number
  avg_predicted_price: number
  max_predicted_price: number
  min_predicted_price: number
  hourly_predictions: HourlyPrice[]
  peak_avg_price: number
}

// ---- Recommendations ----

export interface HourlyOffer {
  hour: string
  suggested_price_cop: number
  reasoning: string
  is_peak_hour: boolean
}

export interface Recommendation {
  id: string
  agent_sic_code: string
  generated_at: string
  prediction_id: string
  narrative: string
  risk_level: 'low' | 'medium' | 'high'
  key_factors: string[]
  hourly_offers: HourlyOffer[]
  llm_model_used: string
  avg_suggested_price: number
  summary: string
}

// ---- Models ----

export interface ModelMetrics {
  rmse: number | null
  mae: number | null
  mape: number | null
  r2: number | null
  coverage_rate: number | null
}

export interface ModelVersion {
  id: string
  name: string
  task: string
  algorithm: string
  version: string
  stage: 'dev' | 'staging' | 'production' | 'archived'
  is_champion: boolean
  metrics: ModelMetrics
  trained_on_days: number
  trained_at: string
  promoted_at: string | null
}

export interface ModelStatus {
  has_champion: boolean
  champion: ModelVersion | null
  total_versions: number
  last_training_at: string | null
}

// ---- Health ----

export interface HealthCheck {
  status: 'ok' | 'degraded'
  version: string
}
