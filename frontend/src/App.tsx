import { useEffect } from 'react'
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import Shell from '@/components/layout/Shell'
import Dashboard from '@/pages/Dashboard'
import Expiry from '@/pages/Expiry'
import Approvals from '@/pages/Approvals'
import BusinessUnits from '@/pages/BusinessUnits'
import Regions from '@/pages/Regions'
import Delayed from '@/pages/Delayed'
import Opportunities from '@/pages/Opportunities'
import ExecutiveView from '@/pages/ExecutiveView'
import DataUploads from '@/pages/DataUploads'
import LoadingScreen from '@/pages/LoadingScreen'
import { useAppStore } from '@/store/appStore'

export default function App() {
  const { darkMode } = useAppStore()

  useEffect(() => {
    document.documentElement.classList.toggle('dark', darkMode)
  }, [darkMode])

  // Dynamic titles based on path
  useEffect(() => {
    const handleTitle = () => {
      const path = window.location.pathname
      const titleMap: Record<string, string> = {
        '/': 'Overview — Mobileum Horizon',
        '/expiry': 'Expiry — Mobileum Horizon',
        '/approvals': 'Approvals — Mobileum Horizon',
        '/business-units': 'Business Units — Mobileum Horizon',
        '/bu': 'Business Units — Mobileum Horizon',
        '/regions': 'Regions — Mobileum Horizon',
        '/delayed': 'Delayed Renewals — Mobileum Horizon',
        '/opportunities': 'Data Explorer — Mobileum Horizon',
        '/explore': 'Data Explorer — Mobileum Horizon',
        '/data-uploads': 'Data Uploads — Mobileum Horizon',
        '/executive': 'Executive View — Mobileum Horizon',
      }
      document.title = titleMap[path] || 'Mobileum Horizon'
    }
    handleTitle()
    window.addEventListener('popstate', handleTitle)
    return () => window.removeEventListener('popstate', handleTitle)
  }, [])

  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
            borderRadius: '12px',
          },
        }}
      />
      <Routes>
        <Route path="/loading" element={<LoadingScreen />} />
        <Route path="/executive" element={<ExecutiveView />} />
        <Route element={<Shell />}>
          <Route path="/" element={<Dashboard />} />
          <Route path="/expiry" element={<Expiry />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/business-units" element={<BusinessUnits />} />
          <Route path="/bu" element={<BusinessUnits />} />
          <Route path="/regions" element={<Regions />} />
          <Route path="/delayed" element={<Delayed />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/explore" element={<Opportunities />} />
          <Route path="/data-uploads" element={<DataUploads />} />

          {/* Redirects from old routes */}
          <Route path="/upload" element={<Navigate to="/data-uploads" replace />} />
          <Route path="/history" element={<Navigate to="/data-uploads" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
