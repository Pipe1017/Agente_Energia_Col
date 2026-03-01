import { BarChart3, Briefcase } from 'lucide-react'
import { useAppStore, type ViewMode } from '@/stores/useAppStore'
import { cn } from '@/lib/utils'

export function ViewToggle() {
  const { viewMode, setViewMode } = useAppStore()

  const options: { mode: ViewMode; label: string; icon: React.ReactNode }[] = [
    { mode: 'executive', label: 'Ejecutivo', icon: <Briefcase className="h-3.5 w-3.5" /> },
    { mode: 'technical', label: 'Técnico',   icon: <BarChart3 className="h-3.5 w-3.5" /> },
  ]

  return (
    <div className="flex items-center rounded-lg border border-zinc-700 bg-zinc-800/50 p-0.5">
      {options.map(({ mode, label, icon }) => (
        <button
          key={mode}
          onClick={() => setViewMode(mode)}
          className={cn(
            'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all',
            viewMode === mode
              ? 'bg-blue-600 text-white shadow-sm'
              : 'text-zinc-400 hover:text-zinc-200',
          )}
        >
          {icon}
          {label}
        </button>
      ))}
    </div>
  )
}
