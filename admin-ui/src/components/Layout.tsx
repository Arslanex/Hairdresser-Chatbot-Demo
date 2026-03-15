import { type ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard,
  CalendarDays,
  MessageSquare,
  Settings,
  Scissors,
  LogOut,
} from 'lucide-react'
import { clearToken } from '../auth'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/appointments', label: 'Randevular', icon: CalendarDays, end: false },
  { to: '/conversations', label: 'Mesajlar', icon: MessageSquare, end: false },
  { to: '/settings', label: 'Ayarlar', icon: Settings, end: false },
]

export default function Layout({ children }: { children: ReactNode }) {
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen bg-zinc-50">
      {/* Sidebar */}
      <aside className="fixed top-0 left-0 h-full w-[60px] md:w-[220px] bg-white border-r border-zinc-200 flex flex-col z-30">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-3 md:px-5 h-14 border-b border-zinc-100">
          <div className="flex items-center justify-center w-7 h-7 bg-rose-500 rounded-lg shrink-0">
            <Scissors size={14} className="text-white" />
          </div>
          <span className="hidden md:block font-semibold text-sm text-zinc-900 tracking-tight truncate">
            İzellik Admin
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 py-3 flex flex-col gap-0.5 px-2">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                [
                  'flex items-center gap-3 px-2 py-2 rounded-lg transition-colors text-sm',
                  isActive
                    ? 'bg-rose-50 text-rose-600 font-medium'
                    : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-50',
                ].join(' ')
              }
            >
              <Icon size={16} className="shrink-0" />
              <span className="hidden md:block">{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Logout */}
        <div className="px-2 py-3 border-t border-zinc-100">
          <button
            onClick={() => { clearToken(); navigate('/login') }}
            className="flex items-center gap-3 px-2 py-2 rounded-lg w-full text-zinc-400 hover:text-zinc-700 hover:bg-zinc-50 transition-colors text-sm"
          >
            <LogOut size={16} className="shrink-0" />
            <span className="hidden md:block">Çıkış</span>
          </button>
        </div>
      </aside>

      {/* Main */}
      <main className="ml-[60px] md:ml-[220px] flex-1 min-h-screen">
        {/* Topbar */}
        <div className="h-14 border-b border-zinc-200 bg-white flex items-center px-6">
          <div className="w-full" />
        </div>
        <div className="p-6">
          {children}
        </div>
      </main>
    </div>
  )
}
