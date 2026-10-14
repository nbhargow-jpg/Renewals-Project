import { NavLink, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  LayoutDashboard,
  Clock,
  Calendar,
  CheckCircle2,
  Building2,
  Globe2,
  Table2,
  Printer,
  ChevronLeft,
  ChevronRight,
  Upload,
} from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/expiry', icon: Calendar, label: 'Expiry' },
  { to: '/approvals', icon: CheckCircle2, label: 'Approvals' },
  { to: '/business-units', icon: Building2, label: 'Business Units' },
  { to: '/regions', icon: Globe2, label: 'Regions' },
  { to: '/delayed', icon: Clock, label: 'Delayed Renewals' },
  { to: '/opportunities', icon: Table2, label: 'Data Explorer' },
  { to: '/data-uploads', icon: Upload, label: 'Data Uploads' },
  { to: '/executive', icon: Printer, label: 'Executive', newTab: true },
]

export default function Sidebar() {
  const { sidebarCollapsed, toggleSidebarCollapsed } = useAppStore()
  const location = useLocation()

  return (
    <motion.aside
      animate={{ width: sidebarCollapsed ? 56 : 232 }}
      transition={{ duration: 0.15, ease: 'easeOut' }}
      className="flex-shrink-0 flex flex-col overflow-hidden select-none border-r z-30 transition-colors"
      style={{
        background: '#12284C',
        borderColor: 'rgba(255, 255, 255, 0.08)',
      }}
    >
      {/* Brand Header */}
      <div className="flex items-center gap-3 px-3.5 h-14 border-b border-white/10 flex-shrink-0">
        <div className="w-8 h-8 rounded-md overflow-hidden flex-shrink-0 bg-white/10 p-1 flex items-center justify-center">
          <img
            src="/assets/logo.png"
            alt="Mobileum"
            className="w-full h-full object-contain"
          />
        </div>
        {!sidebarCollapsed && (
          <div className="overflow-hidden whitespace-nowrap leading-tight flex flex-col justify-center">
            <p className="text-white font-semibold text-sm tracking-tight leading-none mb-1">
              Horizon
            </p>
            <p className="text-slate-400 text-[11px] font-normal tracking-tight leading-none">
              Renewals intelligence
            </p>
          </div>
        )}
      </div>

      {/* Nav List */}
      <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto overflow-x-hidden">
        {NAV_ITEMS.map(({ to, icon: Icon, label, newTab }) => {
          const isHash = to.includes('#')
          const basePath = to.split('#')[0]
          const hash = to.split('#')[1]
          const isActive = isHash
            ? location.pathname === basePath && location.hash === `#${hash}`
            : location.pathname === to

          return (
            <NavLink
              key={to}
              to={to}
              target={newTab ? '_blank' : undefined}
              title={sidebarCollapsed ? label : undefined}
              className={clsx(
                'flex items-center gap-3 px-2.5 py-2 rounded-sm text-xs font-medium transition-colors group relative',
                isActive
                  ? 'bg-white/10 text-white'
                  : 'text-slate-300 hover:text-white hover:bg-white/5'
              )}
            >
              {/* Active left bar */}
              {isActive && (
                <div className="absolute left-0 top-1 bottom-1 w-[3px] bg-[#00A3AD] rounded-r-sm" />
              )}

              <Icon
                className={clsx(
                  'w-[18px] h-[18px] flex-shrink-0',
                  isActive ? 'text-[#00A3AD]' : 'text-slate-400 group-hover:text-slate-200'
                )}
                strokeWidth={1.75}
              />

              {!sidebarCollapsed && (
                <span className="truncate whitespace-nowrap">{label}</span>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Bottom Footer: Collapse toggle */}
      <div className="p-3 border-t border-white/10 flex-shrink-0">
        <button
          type="button"
          onClick={toggleSidebarCollapsed}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-md text-slate-400 hover:text-white hover:bg-white/5 text-xs font-medium transition-colors focus:outline-none"
          title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed ? (
            <ChevronRight className="w-4 h-4" strokeWidth={1.75} />
          ) : (
            <>
              <ChevronLeft className="w-4 h-4" strokeWidth={1.75} />
              <span>Collapse</span>
            </>
          )}
        </button>
      </div>
    </motion.aside>
  )
}
