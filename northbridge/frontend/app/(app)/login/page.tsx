'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { BarChart2, AlertCircle, Eye, EyeOff } from 'lucide-react'
import { api } from '@/lib/api'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const result = await api.auth.login(email, password)
      localStorage.setItem('nb_token', result.access_token)
      router.push('/dashboard')
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Login failed'
      setError(message || 'Invalid email or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#090e1a',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '24px',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background grid */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          backgroundImage:
            'linear-gradient(rgba(30,45,69,0.15) 1px, transparent 1px), linear-gradient(90deg, rgba(30,45,69,0.15) 1px, transparent 1px)',
          backgroundSize: '48px 48px',
          pointerEvents: 'none',
        }}
      />

      {/* Logo */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          marginBottom: '40px',
          position: 'relative',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            backgroundColor: '#1d4ed8',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            borderRadius: '4px',
          }}
        >
          <BarChart2 size={20} color="#fff" />
        </div>
        <div>
          <div style={{ fontWeight: 700, fontSize: '1.1rem', lineHeight: 1.2 }}>
            Northbridge{' '}
            <span style={{ color: '#d97706' }}>Intelligence</span>
          </div>
          <div style={{ fontSize: '0.7rem', color: '#475569', letterSpacing: '0.04em' }}>
            Property Intelligence Platform
          </div>
        </div>
      </div>

      {/* Login card */}
      <div
        style={{
          width: '100%',
          maxWidth: '400px',
          backgroundColor: '#0f1729',
          border: '1px solid #1e2d45',
          borderRadius: '6px',
          padding: '36px',
          position: 'relative',
        }}
      >
        <h1
          style={{
            fontSize: '1.25rem',
            fontWeight: 700,
            color: '#f1f5f9',
            marginBottom: '6px',
          }}
        >
          Sign in to your account
        </h1>
        <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '28px' }}>
          Access the North East property intelligence platform
        </p>

        {error && (
          <div
            style={{
              backgroundColor: 'rgba(185,28,28,0.1)',
              border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: '4px',
              padding: '10px 14px',
              marginBottom: '20px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '0.85rem',
              color: '#fca5a5',
            }}
          >
            <AlertCircle size={15} />
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: '16px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '0.78rem',
                fontWeight: 500,
                color: '#94a3b8',
                marginBottom: '6px',
                letterSpacing: '0.03em',
              }}
            >
              Email address
            </label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              style={{
                width: '100%',
                backgroundColor: '#090e1a',
                border: '1px solid #1e2d45',
                borderRadius: '4px',
                padding: '10px 12px',
                fontSize: '0.9rem',
                color: '#e2e8f0',
                outline: 'none',
                boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: '24px' }}>
            <label
              style={{
                display: 'block',
                fontSize: '0.78rem',
                fontWeight: 500,
                color: '#94a3b8',
                marginBottom: '6px',
                letterSpacing: '0.03em',
              }}
            >
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                style={{
                  width: '100%',
                  backgroundColor: '#090e1a',
                  border: '1px solid #1e2d45',
                  borderRadius: '4px',
                  padding: '10px 40px 10px 12px',
                  fontSize: '0.9rem',
                  color: '#e2e8f0',
                  outline: 'none',
                  boxSizing: 'border-box',
                }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  color: '#64748b',
                  padding: '2px',
                  display: 'flex',
                  alignItems: 'center',
                }}
              >
                {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              backgroundColor: loading ? '#1e3a7a' : '#1d4ed8',
              color: loading ? '#64748b' : '#fff',
              border: '1px solid #2563eb',
              borderRadius: '4px',
              padding: '11px 20px',
              fontSize: '0.9rem',
              fontWeight: 600,
              cursor: loading ? 'not-allowed' : 'pointer',
              transition: 'background-color 0.15s',
            }}
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>

        <div
          style={{
            marginTop: '20px',
            paddingTop: '20px',
            borderTop: '1px solid #1e2d45',
            textAlign: 'center',
            fontSize: '0.8rem',
            color: '#475569',
          }}
        >
          No account?{' '}
          <a href="/#access" style={{ color: '#2563eb', textDecoration: 'none' }}>
            Request access
          </a>
        </div>
      </div>

      <p style={{ marginTop: '24px', fontSize: '0.75rem', color: '#334155', position: 'relative' }}>
        &copy; 2026 Northbridge Capital Partners Ltd
      </p>
    </div>
  )
}
