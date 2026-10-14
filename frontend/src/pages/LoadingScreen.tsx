import { motion } from 'framer-motion'
import { useNavigate } from 'react-router-dom'
import { useEffect } from 'react'

export default function LoadingScreen() {
  const navigate = useNavigate()

  useEffect(() => {
    const t = setTimeout(() => navigate('/'), 2400)
    return () => clearTimeout(t)
  }, [navigate])

  return (
    <div
      className="fixed inset-0 flex flex-col items-center justify-center overflow-hidden z-50 select-none"
      style={{
        background: 'radial-gradient(ellipse at center, #1A3B6F 0%, #12284C 45%, #050D19 100%)',
      }}
    >
      {/* Background glow orbs */}
      <div className="absolute w-96 h-96 rounded-full bg-teal-500/15 blur-3xl pointer-events-none -top-10 -left-10" />
      <div className="absolute w-96 h-96 rounded-full bg-violet-600/15 blur-3xl pointer-events-none -bottom-10 -right-10" />

      {/* Logo container with ambient pulse ring */}
      <motion.div
        initial={{ scale: 0.7, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className="relative mb-8"
      >
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute -inset-4 rounded-md blur-lg"
        />
        <div className="relative w-24 h-24 rounded-md bg-white/10 p-3.5 border border-white/20 shadow-2xl flex items-center justify-center">
          <img
            src="/assets/logo.png"
            alt="Mobileum"
            className="w-full h-full object-contain drop-shadow-xl"
          />
        </div>
      </motion.div>

      {/* Brand typography */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3, duration: 0.5 }}
        className="text-center z-10"
      >
        <h1 className="font-extrabold text-3xl md:text-4xl text-white tracking-tight mb-2">
          Mobileum Horizon
        </h1>
        <p className="text-sm font-semibold tracking-wider uppercase text-teal-400">
          Executive Pipeline Platform
        </p>
      </motion.div>

      {/* Animated progress track */}
      <div className="mt-10 w-64 h-1.5 rounded-full bg-white/10 overflow-hidden relative z-10 shadow-inner">
        <motion.div
          className="h-full rounded-full"
          style={{
            background: 'linear-gradient(90deg, #00A3AD 0%, #00D2DF 50%, #8080FF 100%)',
          }}
          initial={{ x: '-100%' }}
          animate={{ x: '100%' }}
          transition={{ repeat: Infinity, duration: 1.4, ease: 'easeInOut' }}
        />
      </div>

      <motion.p
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.6 }}
        className="mt-4 text-xs font-medium text-slate-400 z-10"
      >
        Loading pipeline snapshots…
      </motion.p>
    </div>
  )
}
