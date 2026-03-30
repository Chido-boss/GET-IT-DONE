'use client'

import { useEffect, useState } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import {
  BarChart2,
  LayoutDashboard,
  Building2,
  FileText,
  MapPin,
  Bell,
  Bookmark,
  Upload,
  LogOut,
  ChevronRight,
  TrendingUp,
} from 'lucide-react'
import type { User } from '@/types'
import { api } from '@/lib/api'

const NAV_SECTIONS = [
  {
    label: 'Intelligence',
    items: [
      { href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
      { href: '/deals', label: 'Deal Pipeline', icon: TrendingUp },
      { href: '/listings', label: 'Listings', icon: Building2 },
      { href: '/planning', label: 'Planning', icon: FileText },
      { href: '/regen', label: 'Regen Zones', icon: MapPin },
    ],
  },
  {
    label: 'Account',
    items: [
      { href: '/alerts', label: 'Alerts', icon: Bell },
      { href: '/saved', label: 'Saved Searches', icon: Bookmark },
    ],
  },
]

const ADMIN_SECTION = {
  label: 'Admin',
  items: [{ href: '/admin', label: 'Import Data', icon: Upload }],
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const pathname = usePathname()
  const [user, setUser] = useState<User | null>(null)
  const [authChecked, setAuthChecked] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('nb_token')
    if (!token) {
      router.replace('/login')
      return
    }
    api.auth
      .me()
      .then((u) => {
        setUser(u)
        setAuthChecked(true)
      })
      .catch(() => {
        localStorage.removeItem('nb_token')
        router.replace('/login')
      })
  }, [router])

  function handleLogout() {
    localStorage.removeItem('nb_token')
    router.push('/login')
  }

  if (!authChecked) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#090e1a',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div style={{ textAlign: 'center' }}>
          <div
            style={{
              width: '32px',
              height: '32px',
              border: '2px solid #1e2d45',
              borderTopColor: '#2563eb',
              borderRadius: '50%',
              animation: 'spin 0.7s linear infinite',
              margin: '0 auto 12px',
            }}
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <div style={{ fontSize: '0.85rem', color: '#64748b' }}>Authenticating…</div>
        </div>
      </div>
    )
  }

  const allSections = user?.is_admin
    ? [...NAV_SECTIONS, ADMIN_SECTION]
    : NAV_SECTIONS

  return (
    <div style={{ display: 'flex', minHeight: '100vh', backgroundColor: '#090e1a' }}>
      {/* ── SIDEBAR ── */}
      <aside
        style={{
          width: '220px',
          minWidth: '220px',
          backgroundColor: '#0f1729',
          borderRight: '1px solid #1e2d45',
          position: 'fixed',
          top: 0,
          left: 0,
          bottom: 0,
          display: 'flex',
          flexDirection: 'column',
          zIndex: 40,
        }}
      >
        {/* Logo */}
        <div
          style={{
            padding: '20px 18px 18px',
            borderBottom: '1px solid #1e2d45',
          }}
        >
          <Link
            href="/dashboard"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '9px',
              textDecoration: 'none',
            }}
          >
            <div
              style={{
                width: '28px',
                height: '28px',
                backgroundColor: '#1d4ed8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '3px',
                flexShrink: 0,
              }}
            >
              <BarChart2 size={15} color="#fff" />
            </div>
            <div style={{ lineHeight: 1.2 }}>
              <div style={{ fontSize: '0.85rem', fontWeight: 700, color: '#e2e8f0' }}>
                Northbridge
              </div>
              <div style={{ fontSize: '0.72rem', fontWeight: 600, color: '#d97706' }}>
                Intelligence
              </div>
            </div>
          </Link>
        </div>

        {/* Navigation */}
        <nav style={{ flex: 1, overflowY: 'auto', padding: '12px 0' }}>
          {allSections.map((section) => (
            <div key={section.label} style={{ marginBottom: '4px' }}>
              <div
                style={{
                  fontSize: '0.63rem',
                  fontWeight: 600,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: '#334155',
                  padding: '10px 18px 5px',
                }}
              >
                {section.label}
              </div>
              {section.items.map((item) => {
                const Icon = item.icon
                const active =
                  pathname === item.href ||
                  (item.href !== '/dashboard' && pathname.startsWith(item.href))
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '9px',
                      padding: '8px 18px',
                      fontSize: '0.85rem',
                      fontWeight: active ? 600 : 400,
                      color: active ? '#e2e8f0' : '#64748b',
                      backgroundColor: active ? 'rgba(37,99,235,0.12)' : 'transparent',
                      borderLeft: active ? '2px solid #2563eb' : '2px solid transparent',
                      textDecoration: 'none',
                      transition: 'all 0.1s',
                    }}
                  >
                    <Icon size={15} />
                    {item.label}
                    {active && (
                      <ChevronRight
                        size={13}
                        style={{ marginLeft: 'auto', color: '#2563eb' }}
                      />
                    )}
                  </Link>
                )
              })}
            </div>
          ))}
        </nav>

        {/* User + logout */}
        <div
          style={{
            borderTop: '1px solid #1e2d45',
            padding: '14px 18px',
          }}
        >
          {user && (
            <div style={{ marginBottom: '10px' }}>
              <div
                style={{
                  fontSize: '0.8rem',
                  fontWeight: 500,
                  color: '#94a3b8',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {user.full_name}
              </div>
              <div
                style={{
                  fontSize: '0.72rem',
                  color: '#475569',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {user.email}
              </div>
              {user.is_admin && (
                <div
                  style={{
                    display: 'inline-block',
                    marginTop: '4px',
                    fontSize: '0.62rem',
                    fontWeight: 700,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    color: '#d97706',
                    backgroundColor: 'rgba(217,119,6,0.1)',
                    border: '1px solid rgba(217,119,6,0.2)',
                    borderRadius: '3px',
                    padding: '1px 6px',
                  }}
                >
                  Admin
                </div>
              )}
            </div>
          )}
          <button
            onClick={handleLogout}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '0.82rem',
              color: '#475569',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px 0',
              width: '100%',
              textAlign: 'left',
              transition: 'color 0.1s',
            }}
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      {/* ── MAIN CONTENT ── */}
      <main
        style={{
          marginLeft: '220px',
          flex: 1,
          padding: '28px',
          minHeight: '100vh',
          backgroundColor: '#090e1a',
        }}
      >
        {children}
      </main>
    </div>
  )
}
