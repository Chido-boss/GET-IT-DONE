'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { api } from '@/lib/api'
import { relativeDate } from '@/lib/utils'
import type { AlertEvent } from '@/types'

export default function AlertsPage() {
  const router = useRouter()
  const [events, setEvents] = useState<AlertEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('nb_token')
    if (!token) { router.push('/login'); return }
    api.alerts.events()
      .then(setEvents)
      .finally(() => setLoading(false))
  }, [router])

  async function markRead(id: string) {
    const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    await fetch(`${BASE}/alerts/events/${id}/read`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('nb_token')}` }
    })
    setEvents(prev => prev.map(e => e.id === id ? { ...e, is_read: true } : e))
  }

  const unread = events.filter(e => !e.is_read).length

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>Alerts</h1>
          <p style={{ color: '#64748b', fontSize: 14, marginTop: 4 }}>
            {unread > 0 ? `${unread} unread alert${unread > 1 ? 's' : ''}` : 'All caught up'}
          </p>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: '#64748b' }}>Loading...</div>
      ) : events.length === 0 ? (
        <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 60, textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🔔</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>No alerts yet</div>
          <div style={{ color: '#64748b', fontSize: 14 }}>
            Alerts will appear here when new high-score deals, price drops, or planning applications match your criteria.
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          {events.map(event => (
            <div
              key={event.id}
              style={{
                background: event.is_read ? '#0f1729' : '#0f1729',
                border: `1px solid ${event.is_read ? '#1e2d45' : '#1d4ed8'}`,
                borderRadius: 6,
                padding: '14px 16px',
                display: 'flex',
                alignItems: 'flex-start',
                gap: 14,
                cursor: 'pointer',
              }}
              onClick={() => !event.is_read && markRead(event.id)}
            >
              <div style={{
                width: 8, height: 8, borderRadius: '50%', marginTop: 5, flexShrink: 0,
                background: event.is_read ? '#1e2d45' : '#3b82f6'
              }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, color: '#e2e8f0', lineHeight: 1.5 }}>{event.message}</div>
                <div style={{ fontSize: 12, color: '#64748b', marginTop: 4 }}>
                  {relativeDate(event.created_at)}
                </div>
              </div>
              {event.listing && (
                <Link
                  href={`/listings/${event.listing.id}`}
                  onClick={e => e.stopPropagation()}
                  style={{
                    fontSize: 12, padding: '4px 10px', borderRadius: 4,
                    background: '#162035', color: '#94a3b8', textDecoration: 'none', whiteSpace: 'nowrap'
                  }}
                >
                  View deal →
                </Link>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
