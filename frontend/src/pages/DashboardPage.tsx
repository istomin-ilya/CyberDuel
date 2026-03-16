import { Navigate, Route, Routes } from 'react-router-dom'
import AppLayout from '@/components/layout/AppLayout'
import MarketsPage from '@/pages/MarketsPage'
import P2PPage from '@/pages/P2PPage'
import PoolPage from '@/pages/PoolPage'
import PortfolioPage from '@/pages/PortfolioPage'

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