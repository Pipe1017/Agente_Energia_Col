import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
import { format, formatDistanceToNow } from 'date-fns'
import { es } from 'date-fns/locale'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatCOP(value: number, decimals = 0): string {
  return new Intl.NumberFormat('es-CO', {
    style: 'currency',
    currency: 'COP',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value)
}

export function formatMWh(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)} TWh`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)} GWh`
  return `${value.toFixed(0)} MWh`
}

export function formatPct(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`
}

export function formatDateTime(iso: string): string {
  return format(new Date(iso), "d MMM yyyy HH:mm", { locale: es })
}

export function formatRelative(iso: string): string {
  return formatDistanceToNow(new Date(iso), { addSuffix: true, locale: es })
}

export function formatHour(iso: string): string {
  return format(new Date(iso), 'HH:mm')
}

export function hydrologyColor(status: string): string {
  switch (status) {
    case 'crítica': return 'text-red-400'
    case 'baja':    return 'text-yellow-400'
    case 'normal':  return 'text-blue-400'
    case 'alta':    return 'text-emerald-400'
    default:        return 'text-gray-400'
  }
}

export function hydrologyBg(status: string): string {
  switch (status) {
    case 'crítica': return 'bg-red-500/10 border-red-500/30'
    case 'baja':    return 'bg-yellow-500/10 border-yellow-500/30'
    case 'normal':  return 'bg-blue-500/10 border-blue-500/30'
    case 'alta':    return 'bg-emerald-500/10 border-emerald-500/30'
    default:        return 'bg-zinc-800/50 border-zinc-700'
  }
}

export function riskColor(level: string): string {
  switch (level) {
    case 'low':    return 'text-emerald-400'
    case 'medium': return 'text-yellow-400'
    case 'high':   return 'text-red-400'
    default:       return 'text-gray-400'
  }
}

export function riskLabel(level: string): string {
  switch (level) {
    case 'low':    return 'Bajo'
    case 'medium': return 'Medio'
    case 'high':   return 'Alto'
    default:       return level
  }
}

export function riskProfileLabel(profile: string): string {
  switch (profile) {
    case 'conservative': return 'Conservador'
    case 'moderate':     return 'Moderado'
    case 'aggressive':   return 'Agresivo'
    default:             return profile
  }
}
