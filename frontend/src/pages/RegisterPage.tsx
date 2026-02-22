import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '@/store/authStore'

export default function RegisterPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [localError, setLocalError] = useState('')
  const { register, isLoading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLocalError('')

    if (password !== confirm) {
      setLocalError('Passwords do not match')
      return
    }

    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters')
      return
    }

    await register(email, password)
    if (!useAuthStore.getState().error) {
      navigate('/')
    }
  }

  const displayError = localError || error

  const inputStyle = {
    background: '#07090f',
    border: '1px solid rgba(0,212,255,0.08)',
    color: '#e2e8f0',
    fontFamily: 'JetBrains Mono, monospace',
  }

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = '#00d4ff'
    e.target.style.boxShadow = '0 0 0 3px rgba(0,212,255,0.1)'
  }

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    e.target.style.borderColor = 'rgba(0,212,255,0.08)'
    e.target.style.boxShadow = 'none'
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center relative overflow-hidden">

      {/* Grid background */}
      <div className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage: `
            linear-gradient(rgba(0,212,255,0.03) 1px, transparent 1px),
            linear-gradient(90deg, rgba(0,212,255,0.03) 1px, transparent 1px)
          `,
          backgroundSize: '40px 40px'
        }}
      />

      {/* Glow */}
      <div className="absolute inset-0 pointer-events-none"
        style={{
          background: 'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(0,212,255,0.04) 0%, transparent 70%)'
        }}
      />

      {/* Card */}
      <div className="relative z-10 w-full max-w-sm mx-4">
        <div
          className="rounded-lg p-10"
          style={{
            background: '#0d1117',
            border: '1px solid rgba(0,212,255,0.1)',
            boxShadow: '0 24px 64px rgba(0,0,0,0.6)',
          }}
        >
          {/* Logo */}
          <div className="flex flex-col items-center mb-8">
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center mb-3"
              style={{
                background: 'rgba(0,212,255,0.08)',
                border: '1px solid rgba(0,212,255,0.25)',
                boxShadow: '0 0 24px rgba(0,212,255,0.15)',
              }}
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                <path d="M12 2L4 7v5c0 5 4 9 8 10 4-1 8-5 8-10V7L12 2z"
                  stroke="#00d4ff" strokeWidth="1.5" fill="rgba(0,212,255,0.08)" />
                <path d="M9 12l2 2 4-4"
                  stroke="#00d4ff" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <div className="text-lg font-black tracking-wide">CyberDuel</div>
            <div className="text-xs tracking-widest mt-1"
              style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
              CREATE ACCOUNT
            </div>
          </div>

          {/* Error */}
          {displayError && (
            <div
              className="mb-4 px-4 py-3 rounded-lg text-sm"
              style={{ background: 'rgba(255,51,102,0.1)', border: '1px solid rgba(255,51,102,0.2)', color: '#ff3366' }}
            >
              {displayError}
              <button onClick={() => { setLocalError(''); clearError() }} className="float-right opacity-60 hover:opacity-100">✕</button>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <div>
              <div className="text-xs tracking-widest mb-2 uppercase"
                style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
                Email
              </div>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="user@example.com"
                required
                className="w-full px-4 py-3 rounded-lg text-sm outline-none transition-all"
                style={inputStyle}
                onFocus={handleFocus}
                onBlur={handleBlur}
              />
            </div>

            <div>
              <div className="text-xs tracking-widest mb-2 uppercase"
                style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
                Password
              </div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-4 py-3 rounded-lg text-sm outline-none transition-all"
                style={inputStyle}
                onFocus={handleFocus}
                onBlur={handleBlur}
              />
            </div>

            <div>
              <div className="text-xs tracking-widest mb-2 uppercase"
                style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
                Confirm Password
              </div>
              <input
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="••••••••"
                required
                className="w-full px-4 py-3 rounded-lg text-sm outline-none transition-all"
                style={inputStyle}
                onFocus={handleFocus}
                onBlur={handleBlur}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-3 rounded-lg font-bold tracking-wide text-sm mt-2 transition-all"
              style={{
                background: isLoading ? 'rgba(0,212,255,0.5)' : '#00d4ff',
                color: '#07090f',
                boxShadow: isLoading ? 'none' : '0 0 20px rgba(0,212,255,0.35)',
                cursor: isLoading ? 'not-allowed' : 'pointer',
              }}
            >
              {isLoading ? 'Creating account...' : 'Join the Protocol'}
            </button>
          </form>

          {/* Footer */}
          <div className="mt-6 text-center text-xs" style={{ color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}>
            Already have an account?{' '}
            <Link to="/login" style={{ color: '#00d4ff' }}>
              Login →
            </Link>
          </div>

          <div
            className="mt-6 pt-4 flex justify-between text-xs"
            style={{ borderTop: '1px solid rgba(0,212,255,0.08)', color: '#4a5568', fontFamily: 'JetBrains Mono, monospace' }}
          >
            <span>🎮 1,000 demo credits on sign up</span>
            <span style={{ color: '#00ff88' }}>● Live</span>
          </div>
        </div>
      </div>
    </div>
  )
}