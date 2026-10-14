import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Lock, LogOut, ShieldCheck, X, Loader2 } from 'lucide-react'
import { useAppStore } from '@/store/appStore'
import { adminLogin, adminLogout } from '@/api/client'
import { showToast } from '@/components/ui/Toast'

export default function AdminAuthModal() {
  const { isAdmin, setIsAdmin } = useAppStore()
  const [isOpen, setIsOpen] = useState(false)
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim()) return
    setLoading(true)
    setError(null)
    try {
      const res = await adminLogin(password)
      setIsAdmin(true, res.token)
      setPassword('')
      setIsOpen(false)
      showToast.success('Admin Signed In', 'Full upload and management permissions unlocked.')
    } catch (err: any) {
      const msg = err.response?.data?.detail || 'Invalid admin credentials or server configuration.'
      setError(msg)
      showToast.error('Sign In Failed', msg)
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = async () => {
    try {
      await adminLogout()
    } catch (_) {}
    setIsAdmin(false, null)
    showToast.info('Signed Out', 'Returned to read-only viewer mode.')
  }

  return (
    <>
      {isAdmin ? (
        <div className="h-9 px-3 rounded-md bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 text-xs font-medium inline-flex items-center gap-1.5 flex-shrink-0">
          <ShieldCheck className="w-3.5 h-3.5 flex-shrink-0" />
          <span className="hidden xl:inline">Admin</span>
          <button
            type="button"
            onClick={handleLogout}
            title="Sign out as administrator"
            className="ml-1 hover:text-red-500 transition-colors p-0.5 rounded"
            id="admin-sign-out-btn"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => {
            setError(null)
            setIsOpen(true)
          }}
          className="h-9 px-3 rounded-md bg-[var(--bg-secondary)] hover:bg-[var(--bg-card)] border border-[var(--border)] text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors inline-flex items-center gap-1.5 flex-shrink-0 focus:outline-none"
          id="admin-sign-in-btn"
          title="Admin sign in"
        >
          <Lock className="w-3.5 h-3.5 text-amber-500 flex-shrink-0" />
          <span className="hidden xl:inline">Admin sign in</span>
        </button>
      )}

      {/* Admin Sign-In Modal */}
      <AnimatePresence>
        {isOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60">
            <motion.div
              initial={{ opacity: 0, scale: 0.97, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.97, y: 8 }}
              transition={{ duration: 0.15, ease: 'easeOut' }}
              className="w-full max-w-md bg-[var(--bg-card)] border border-[var(--border)] rounded-2xl shadow-xl p-6 relative overflow-hidden"
            >
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="absolute right-4 top-4 p-1.5 rounded-md text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-3 mb-5">
                <div className="w-9 h-9 rounded-md bg-[var(--bg-secondary)] border border-[var(--border)] flex items-center justify-center text-amber-600 dark:text-amber-400">
                  <Lock className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="font-semibold text-sm text-[var(--text-primary)] tracking-tight">
                    Administrator Authentication
                  </h3>
                  <p className="text-xs text-[var(--text-muted)] mt-0.5">
                    Authorized access for data ingestion and snapshot management
                  </p>
                </div>
              </div>

              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="block text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)] mb-1">
                    Admin Password
                  </label>
                  <div>
                    <input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter administrator password..."
                      className="w-full px-3 py-2 rounded-md text-xs bg-[var(--bg-secondary)] border border-[var(--border)] text-[var(--text-primary)] outline-none focus:border-[#00A3AD] transition-colors font-mono"
                      autoFocus
                      required
                      id="admin-password-input"
                    />
                  </div>
                </div>

                {error && (
                  <div className="p-2.5 rounded-md bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-medium flex items-center gap-2">
                    <X className="w-3.5 h-3.5 flex-shrink-0 text-rose-500" />
                    <span>{error}</span>
                  </div>
                )}

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-[var(--border)]">
                  <button
                    type="button"
                    onClick={() => setIsOpen(false)}
                    className="px-3.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] rounded-md transition-colors border border-transparent"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="flex items-center gap-2 px-4 py-1.5 rounded-md bg-[#12284C] hover:bg-[#1B365D] text-white font-medium text-xs transition-colors disabled:opacity-50"
                    id="admin-submit-login-btn"
                  >
                    {loading && <Loader2 className="w-3 h-3 animate-spin" />}
                    <span>Authenticate as Administrator</span>
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </>
  )
}
