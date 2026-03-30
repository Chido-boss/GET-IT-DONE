'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { api } from '@/lib/api'
import { formatPrice, formatDiscount, propertyTypeLabel, relativeDate } from '@/lib/utils'
import { ScoreBadge } from '@/components/ui/ScoreBadge'
import { SignalChip } from '@/components/ui/SignalChip'
import type { Listing } from '@/types'

export default function DealDetailPage() {
  const { id } = useParams<{ id: string }>()
  const router = useRouter()
  const [listing, setListing] = useState<Listing | null>(null)
  const [loading, setLoading] = useState(true)
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('nb_token')
    if (!token) { router.push('/login'); return }
    api.listings.get(id)
      .then(setListing)
      .catch(() => router.push('/listings'))
      .finally(() => setLoading(false))
  }, [id, router])

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '60vh', color: '#64748b' }}>
      Loading deal...
    </div>
  )
  if (!listing) return null

  const score = listing.score
  const drivers = score?.score_drivers || []
  const discount = score?.discount_pct
  const estValue = score?.estimated_fair_value

  const signals: string[] = []
  if (discount && discount >= 10) signals.push('bmv')
  if ((score?.distress_score || 0) >= 30) signals.push('distress')
  if ((score?.regeneration_score || 0) >= 20) signals.push('regen')
  if ((score?.planning_score || 0) >= 20) signals.push('planning')
  if ((listing.price_reduction_count || 0) >= 1) signals.push('reduced')

  async function handleFlag() {
    await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/listings/${id}/flag`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('nb_token')}` }
    })
    setListing(prev => prev ? { ...prev, is_flagged: !prev.is_flagged } : prev)
  }

  return (
    <div>
      {/* Back nav */}
      <div style={{ marginBottom: 20 }}>
        <Link href="/listings" style={{ fontSize: 13, color: '#64748b', textDecoration: 'none' }}>
          ← Back to deals
        </Link>
      </div>

      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>{listing.address}</h1>
            <div style={{ color: '#64748b', fontSize: 14, display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <span>{listing.postcode}</span>
              {listing.council && <span>· {listing.council}</span>}
              <span>· {propertyTypeLabel(listing.property_type)}</span>
              {listing.bedrooms && <span>· {listing.bedrooms} bed</span>}
              {listing.tenure && <span style={{ textTransform: 'capitalize' }}>· {listing.tenure}</span>}
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button onClick={handleFlag} style={{
              padding: '8px 14px', borderRadius: 4, border: '1px solid #1e2d45',
              background: listing.is_flagged ? 'rgba(245,158,11,0.15)' : '#0f1729',
              color: listing.is_flagged ? '#d97706' : '#94a3b8', cursor: 'pointer', fontSize: 13
            }}>
              {listing.is_flagged ? '★ Flagged' : '☆ Flag deal'}
            </button>
            {listing.url && (
              <a href={listing.url} target="_blank" rel="noreferrer" style={{
                padding: '8px 14px', borderRadius: 4, background: '#1d4ed8',
                color: 'white', fontSize: 13, textDecoration: 'none'
              }}>
                View listing →
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Price row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: 12, marginBottom: 24 }}>
        <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '16px 18px' }}>
          <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Asking Price</div>
          <div style={{ fontSize: 26, fontWeight: 700, color: '#e2e8f0' }}>{formatPrice(listing.asking_price)}</div>
        </div>
        {estValue && (
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '16px 18px' }}>
            <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Est. Market Value</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: '#d97706' }}>{formatPrice(estValue)}</div>
          </div>
        )}
        {discount != null && (
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '16px 18px' }}>
            <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Discount</div>
            <div style={{ fontSize: 26, fontWeight: 700, color: discount > 0 ? '#10b981' : '#ef4444' }}>
              {formatDiscount(discount)}
            </div>
          </div>
        )}
        {score && (
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '16px 18px' }}>
            <div style={{ fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: 6 }}>Deal Score</div>
            <div style={{ fontSize: 26, fontWeight: 700 }}>
              <ScoreBadge score={score.overall_score} large />
            </div>
          </div>
        )}
      </div>

      {/* Signal chips */}
      {signals.length > 0 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 24 }}>
          {signals.map(s => <SignalChip key={s} type={s as any} />)}
        </div>
      )}

      {/* Main 2-col grid */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: 20, alignItems: 'start' }}>

        {/* LEFT */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Score breakdown */}
          {score && (
            <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 16 }}>Score Breakdown</h3>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                {[
                  { label: 'BMV', value: score.bmv_score },
                  { label: 'Distress', value: score.distress_score },
                  { label: 'Momentum', value: score.momentum_score },
                  { label: 'Planning', value: score.planning_score },
                  { label: 'Regeneration', value: score.regeneration_score },
                  { label: 'Confidence', value: score.confidence_score },
                ].map(({ label, value }) => (
                  <div key={label}>
                    <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>{label}</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{ flex: 1, height: 4, background: '#162035', borderRadius: 2 }}>
                        <div style={{
                          height: '100%', borderRadius: 2,
                          width: `${value}%`,
                          background: value >= 60 ? '#10b981' : value >= 35 ? '#d97706' : '#334155'
                        }} />
                      </div>
                      <span style={{ fontSize: 12, fontWeight: 600, color: '#e2e8f0', minWidth: 24 }}>{Math.round(value)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Score drivers */}
          {drivers.length > 0 && (
            <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 14 }}>Why this score</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {drivers.map((d, i) => (
                  <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '10px 12px', background: '#162035', borderRadius: 4 }}>
                    <span style={{ fontSize: 16 }}>{d.icon}</span>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13, color: '#e2e8f0' }}>{d.label}</div>
                      <div style={{ fontSize: 11, color: '#64748b', marginTop: 2 }}>Impact: {Math.round(d.impact)}/100</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Description */}
          {listing.description && (
            <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 20 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>Listing Description</h3>
              <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{listing.description}</p>
            </div>
          )}

          {/* Note */}
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 20 }}>
            <h3 style={{ fontSize: 14, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>Add Note</h3>
            <textarea
              value={note}
              onChange={e => setNote(e.target.value)}
              placeholder="Due diligence notes, offer strategy, contacts..."
              rows={4}
              style={{
                width: '100%', background: '#162035', border: '1px solid #1e2d45',
                color: '#e2e8f0', padding: '10px 12px', borderRadius: 4, fontSize: 13,
                resize: 'vertical', fontFamily: 'inherit'
              }}
            />
            <button
              onClick={async () => {
                setSaving(true)
                await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/listings/${id}/notes`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('nb_token')}` },
                  body: JSON.stringify({ notes: note })
                })
                setSaving(false)
              }}
              disabled={saving}
              style={{
                marginTop: 10, padding: '8px 16px', background: '#1d4ed8',
                color: 'white', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 13
              }}
            >
              {saving ? 'Saving...' : 'Save note'}
            </button>
          </div>
        </div>

        {/* RIGHT */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Key details */}
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 18 }}>
            <h3 style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>Property Details</h3>
            {[
              ['Type', propertyTypeLabel(listing.property_type)],
              ['Bedrooms', listing.bedrooms ?? '—'],
              ['Bathrooms', listing.bathrooms ?? '—'],
              ['Tenure', listing.tenure || '—'],
              ['Status', listing.status],
              ['Agent', listing.agent_name || '—'],
              ['Phone', listing.agent_phone || '—'],
              ['Listed', listing.date_listed ? relativeDate(listing.date_listed) : '—'],
              ['DOM', listing.days_on_market ? `${listing.days_on_market} days` : '—'],
              ['Price reductions', listing.price_reduction_count || 0],
              ['Source', listing.source],
            ].map(([label, value]) => (
              <div key={label as string} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid #162035', fontSize: 13 }}>
                <span style={{ color: '#64748b' }}>{label}</span>
                <span style={{ color: '#e2e8f0', fontWeight: 500 }}>{String(value)}</span>
              </div>
            ))}
          </div>

          {/* Price history */}
          {listing.previous_price && (
            <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 18 }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>Price History</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: '#64748b' }}>Original</span>
                  <span style={{ color: '#94a3b8', textDecoration: 'line-through' }}>{formatPrice(listing.previous_price)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: '#64748b' }}>Current</span>
                  <span style={{ color: '#10b981', fontWeight: 700 }}>{formatPrice(listing.asking_price)}</span>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 13 }}>
                  <span style={{ color: '#64748b' }}>Reduction</span>
                  <span style={{ color: '#10b981' }}>
                    {formatDiscount(((listing.previous_price - listing.asking_price) / listing.previous_price) * 100)}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Comparable sold prices */}
          {score?.avg_comparable_price && (
            <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 18 }}>
              <h3 style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 12 }}>Market Comparables</h3>
              <div style={{ fontSize: 13, color: '#64748b', marginBottom: 8 }}>Land Registry average</div>
              <div style={{ fontSize: 22, fontWeight: 700, color: '#d97706' }}>{formatPrice(score.avg_comparable_price)}</div>
              {discount != null && (
                <div style={{ marginTop: 8, fontSize: 13, color: discount > 0 ? '#10b981' : '#ef4444' }}>
                  This listing is {Math.abs(discount).toFixed(1)}% {discount > 0 ? 'below' : 'above'} average
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
