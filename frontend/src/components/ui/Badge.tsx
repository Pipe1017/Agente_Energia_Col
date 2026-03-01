import { cn } from '@/lib/utils'

type Variant = 'default' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'

const variants: Record<Variant, string> = {
  default:  'bg-zinc-800 text-zinc-300 border-zinc-700',
  success:  'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  warning:  'bg-yellow-500/10 text-yellow-400 border-yellow-500/30',
  danger:   'bg-red-500/10 text-red-400 border-red-500/30',
  info:     'bg-blue-500/10 text-blue-400 border-blue-500/30',
  neutral:  'bg-zinc-700/50 text-zinc-400 border-zinc-600',
}

interface BadgeProps {
  children: React.ReactNode
  variant?: Variant
  className?: string
  dot?: boolean
}

export function Badge({ children, variant = 'default', className, dot }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        variants[variant],
        className,
      )}
    >
      {dot && (
        <span className={cn('h-1.5 w-1.5 rounded-full', {
          'bg-emerald-400': variant === 'success',
          'bg-yellow-400': variant === 'warning',
          'bg-red-400': variant === 'danger',
          'bg-blue-400': variant === 'info',
          'bg-zinc-400': variant === 'neutral' || variant === 'default',
        })} />
      )}
      {children}
    </span>
  )
}
