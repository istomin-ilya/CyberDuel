import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import MarketsPage from '@/pages/MarketsPage'
import P2PPage from '@/pages/P2PPage'
import PoolPage from '@/pages/PoolPage'

// Заглушки страниц — заменим на Days 23-24



function PortfolioPage() {
  return <div style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace', fontSize: '12px' }}>Portfolio — coming soon</div>
}

export default function DashboardPage() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/markets" replace />} />
        <Route path="markets" element={<MarketsPage />} />
        <Route path="p2p" element={<P2PPage />} />
        <Route path="pool" element={<PoolPage />} />
        <Route path="portfolio" element={<PortfolioPage />} />
      </Route>
    </Routes>
  )
}