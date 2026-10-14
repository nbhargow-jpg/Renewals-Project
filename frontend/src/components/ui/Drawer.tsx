import React, { useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X } from 'lucide-react'
import clsx from 'clsx'

interface DrawerProps {
  open?: boolean
  isOpen?: boolean
  onClose: () => void
  title?: string
  subtitle?: string
  children: React.ReactNode
  footer?: React.ReactNode
  width?: string
  size?: 'sm' | 'md' | 'lg' | 'xl'
  position?: 'right' | 'left'
}

export function Drawer({
  open,
  isOpen,
  onClose,
  title,
  subtitle,
  children,
  footer,
  width,
  size = 'md',
  position = 'right',
}: DrawerProps) {
  const isDrawerOpen = open ?? isOpen ?? false

  const sizeWidthMap = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-xl',
    xl: 'max-w-3xl',
  }

  const effectiveWidth = width || sizeWidthMap[size] || 'max-w-md'

  // Lock body scroll when open
  useEffect(() => {
    if (isDrawerOpen) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [isDrawerOpen])

  // ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isDrawerOpen) onClose()
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isDrawerOpen, onClose])

  const slideX = position === 'right' ? '100%' : '-100%'

  return (
    <AnimatePresence>
      {isDrawerOpen && (
        <div className="fixed inset-0 z-50 overflow-hidden flex">
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.14 }}
            onClick={onClose}
            className="fixed inset-0 bg-black/50"
          />

          {/* Drawer Panel */}
          <motion.div
            initial={{ x: slideX }}
            animate={{ x: 0 }}
            exit={{ x: slideX }}
            transition={{ duration: 0.16, ease: 'easeOut' }}
            className={clsx(
              'relative z-10 w-full bg-[var(--bg-card)] border-l border-[var(--border)] shadow-elevation flex flex-col h-full',
              position === 'right' ? 'rounded-l-2xl' : 'rounded-r-2xl',
              effectiveWidth,
              position === 'right' ? 'ml-auto' : 'mr-auto'
            )}
          >
            {/* Header */}
            <div className={clsx("flex items-center justify-between px-6 py-4 border-b border-[var(--border)] bg-[var(--bg-secondary)]", position === 'right' ? 'rounded-tl-2xl' : 'rounded-tr-2xl')}>
              <div>
                {title && (
                  <h3 className="font-semibold text-base text-[var(--text-primary)]">
                    {title}
                  </h3>
                )}
                {subtitle && (
                  <p className="text-xs text-[var(--text-muted)] mt-0.5">
                    {subtitle}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={onClose}
                className="w-8 h-8 rounded-md flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-card)] transition-colors focus:outline-none"
              >
                <X className="w-4 h-4" strokeWidth={1.75} />
              </button>
            </div>

            {/* Content Body */}
            <div className="flex-1 overflow-y-auto px-6 py-5">
              {children}
            </div>

            {/* Footer */}
            {footer && (
              <div className="px-6 py-4 border-t border-[var(--border)] bg-[var(--bg-secondary)]/30">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}

export default Drawer
