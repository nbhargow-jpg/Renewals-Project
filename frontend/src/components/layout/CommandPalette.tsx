import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Search,
  LayoutDashboard, Clock,
  TrendingUp,
  Calendar,
  CheckCircle2,
  Building2,
  Globe2,
  Table2,
  History,
  Sparkles,
  Upload,
  Printer,
  Palette,
  SunMoon,
  X,
} from 'lucide-react'
import { useAppStore } from '@/store/appStore'

interface CommandItem {
  id: string
  label: string
  category: 'Navigation' | 'Actions'
  icon: any
  to?: string
  action?: () => void
}

export default function CommandPalette() {
  const { commandPaletteOpen, setCommandPaletteOpen, toggleDarkMode, darkMode } =
    useAppStore()
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState(0)
  const inputRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()

  const COMMANDS: CommandItem[] = [
    { id: 'overview', label: 'Overview', category: 'Navigation', icon: LayoutDashboard, to: '/' },
    { id: 'expiry', label: 'Expiry Quarters', category: 'Navigation', icon: Calendar, to: '/expiry' },
    { id: 'approvals', label: 'Approvals Status', category: 'Navigation', icon: CheckCircle2, to: '/approvals' },
    { id: 'bu', label: 'Business Units', category: 'Navigation', icon: Building2, to: '/business-units' },
    { id: 'regions', label: 'Top Regions', category: 'Navigation', icon: Globe2, to: '/regions' },
    { id: 'delayed', label: 'Delayed Renewals', category: 'Navigation', icon: Clock, to: '/delayed' },

    { id: 'explore', label: 'Data Explorer', category: 'Navigation', icon: Table2, to: '/opportunities' },
    { id: 'data-uploads', label: 'Data Uploads & History', category: 'Navigation', icon: Upload, to: '/data-uploads' },
    { id: 'executive', label: 'Executive View (Print)', category: 'Navigation', icon: Printer, to: '/executive' },
    {
      id: 'theme',
      label: darkMode ? 'Switch to Light Theme' : 'Switch to Dark Theme',
      category: 'Actions',
      icon: SunMoon,
      action: toggleDarkMode,
    },
  ]

  const filtered = COMMANDS.filter((c) =>
    c.label.toLowerCase().includes(query.toLowerCase())
  )

  useEffect(() => {
    if (commandPaletteOpen) {
      setQuery('')
      setSelected(0)
      setTimeout(() => inputRef.current?.focus(), 50)
    }
  }, [commandPaletteOpen])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      // Global shortcut Ctrl+K or Cmd+K
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setCommandPaletteOpen(!commandPaletteOpen)
        return
      }

      if (!commandPaletteOpen) return

      if (e.key === 'Escape') {
        setCommandPaletteOpen(false)
      } else if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelected((s) => Math.min(s + 1, filtered.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelected((s) => Math.max(s - 1, 0))
      } else if (e.key === 'Enter' && filtered[selected]) {
        e.preventDefault()
        const cmd = filtered[selected]
        if (cmd.action) {
          cmd.action()
        } else if (cmd.to) {
          navigate(cmd.to)
        }
        setCommandPaletteOpen(false)
      }
    }

    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [commandPaletteOpen, filtered, selected, navigate, setCommandPaletteOpen])

  return (
    <AnimatePresence>
      {commandPaletteOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden flex items-start justify-center pt-24 px-4">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60"
            onClick={() => setCommandPaletteOpen(false)}
          />

          {/* Palette Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: -16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: -16 }}
            transition={{ duration: 0.18, ease: 'easeOut' }}
            className="relative z-10 w-full max-w-lg rounded-md overflow-hidden shadow-2xl bg-[var(--bg-card)] border border-[var(--border)]"
          >
            {/* Search Input Bar */}
            <div className="flex items-center gap-3 px-4 py-3.5 border-b border-[var(--border)] bg-[var(--bg-secondary)]/30">
              <Search className="w-5 h-5 text-teal-500 flex-shrink-0" />
              <input
                ref={inputRef}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setSelected(0)
                }}
                placeholder="Search commands, views, or actions (e.g. Pipeline, Dark Theme)..."
                className="flex-1 bg-transparent text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] outline-none"
                id="command-palette-input"
              />
              <button
                type="button"
                onClick={() => setCommandPaletteOpen(false)}
                className="w-6 h-6 rounded flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Results List */}
            <ul className="py-2 max-h-80 overflow-y-auto divide-y divide-[var(--border-subtle)]">
              {filtered.map((cmd, i) => {
                const Icon = cmd.icon
                const isSel = i === selected
                return (
                  <li key={cmd.id}>
                    <button
                      type="button"
                      className={`w-full flex items-center justify-between px-4 py-2.5 text-sm text-left transition-colors ${
                        isSel
                          ? 'bg-teal-500/12 text-teal-600 dark:text-teal-400 font-semibold'
                          : 'text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]'
                      }`}
                      onMouseEnter={() => setSelected(i)}
                      onClick={() => {
                        if (cmd.action) cmd.action()
                        else if (cmd.to) navigate(cmd.to)
                        setCommandPaletteOpen(false)
                      }}
                    >
                      <div className="flex items-center gap-3">
                        <Icon
                          className={`w-4 h-4 ${
                            isSel ? 'text-teal-500' : 'text-[var(--text-muted)]'
                          }`}
                        />
                        <span>{cmd.label}</span>
                      </div>
                      <span className="text-[10px] text-[var(--text-muted)] font-normal uppercase tracking-wider">
                        {cmd.category}
                      </span>
                    </button>
                  </li>
                )
              })}
              {filtered.length === 0 && (
                <li className="px-4 py-8 text-center text-sm text-[var(--text-muted)]">
                  No matching commands found for "{query}"
                </li>
              )}
            </ul>

            {/* Keyboard Footer */}
            <div className="px-4 py-2.5 border-t border-[var(--border)] bg-[var(--bg-secondary)]/50 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
              <div className="flex items-center gap-3">
                <span>
                  <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border)] font-mono text-[10px]">
                    ↑↓
                  </kbd>{' '}
                  Navigate
                </span>
                <span>
                  <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border)] font-mono text-[10px]">
                    ↵
                  </kbd>{' '}
                  Select
                </span>
                <span>
                  <kbd className="px-1.5 py-0.5 rounded bg-[var(--bg-card)] border border-[var(--border)] font-mono text-[10px]">
                    ESC
                  </kbd>{' '}
                  Close
                </span>
              </div>
              <span className="font-semibold text-teal-500">Mobileum Intelligence</span>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
