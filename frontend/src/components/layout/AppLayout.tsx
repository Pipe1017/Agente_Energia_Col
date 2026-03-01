import { Outlet, NavLink } from 'react-router-dom'
import { Header } from './Header'
import { LayoutDashboard, User, Brain } from 'lucide-react'
import { cn } from '@/lib/utils'

function NavBar() {
  const links = [
    { to: '/',        label: 'Dashboard', icon: <LayoutDashboard className="h-4 w-4" />, end: true },
    { to: '/profile', label: 'Perfil',    icon: <User className="h-4 w-4" />, end: false },
    { to: '/models',  label: 'Modelos',   icon: <Brain className="h-4 w-4" />, end: false },
  ]

  return (
    <nav className="border-b border-zinc-800 bg-zinc-900/30">
      <div className="container mx-auto max-w-7xl px-4">
        <div className="flex gap-0">
          {links.map(({ to, label, icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-2 border-b-2 px-4 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-zinc-500 hover:text-zinc-300',
                )
              }
            >
              {icon}
              <span className="hidden sm:inline">{label}</span>
            </NavLink>
          ))}
        </div>
      </div>
    </nav>
  )
}

export function AppLayout() {
  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      <Header />
      <NavBar />
      <main className="container mx-auto max-w-7xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
