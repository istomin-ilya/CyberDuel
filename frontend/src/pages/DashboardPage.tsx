import { useAuthStore } from '@/store/authStore'
import { useNavigate } from 'react-router-dom'

export default function DashboardPage() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex items-center justify-center"
      style={{ background: '#07090f' }}>
      <div className="text-center">
        <div className="text-xs tracking-widest mb-4"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          CONNECTED AS
        </div>
        <div className="text-2xl font-black mb-1">{user?.email}</div>
        <div className="text-sm mb-1"
          style={{ color: '#00d4ff', fontFamily: 'JetBrains Mono, monospace' }}>
          {parseFloat(user?.balance_available || '0').toFixed(2)} CR
        </div>
        <div className="text-xs mb-8"
          style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
          Balance available
        </div>
        <button
          onClick={handleLogout}
          className="px-6 py-2 rounded-lg text-sm font-bold tracking-wide transition-all"
          style={{
            border: '1px solid rgba(0,212,255,0.15)',
            color: '#4a5568',
            background: 'transparent',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = '#ff3366'
            e.currentTarget.style.color = '#ff3366'
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'rgba(0,212,255,0.15)'
            e.currentTarget.style.color = '#4a5568'
          }}
        >
          Disconnect
        </button>
      </div>
    </div>
  )
}