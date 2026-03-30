'use client'

import { useEffect, useState } from 'react'
import { useRouter, useParams } from 'next/navigation'
import Link from 'next/link'
import { formatPrice } from '@/lib/utils'

const TIER_STYLE: Record<string, { bg: string; color: string; label: string }> = {
  S: { bg: 'rgba(16,185,129,0.12)', color: '#10b981', label: 'S-Tier — Elite deal' },
  A: { bg: 'rgba(245,158,11,0.12)', color: '#d97706', label: 'A-Tier — Strong deal' },
  B: { bg: 'rgba(37,99,235,0.12)', color: '#3b82f6', label: 'B-Tier — Solid deal' },
  C: { bg: 'rgba(100,116,139,0.1)', color: '#64748b', label: 'C-Tier — Watch & review' },
}

function ScoreBar({ label, value, max = 100, color }: { label: string; value: number; max?: number; color: string }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
        <span style={{ fontSize: 12, color: '#94a3b8' }}>{label}</span>
        <span style={{ fontSize: 12, fontWeight: 700, color }}>{value.toFixed(0)}</span>
      </div>
      <div style={{ height: 5, background: '#1e2d45', borderRadius: 3 }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 3, transition: 'width 0.5s ease' }} />
      </div>
    </div>
  )
}

function Row({ label, value, highlight }: { label: string; value: React.ReactNode; highlight?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #0f1729' }}>
      <span style={{ fontSize: 13, color: '#64748b' }}>{label}</span>
      <span style={{ fontSize: 13, fontWeight: highlight ? 700 : 500, color: highlight ? '#e2e8f0' : '#94a3b8' }}>{value}</span>
    </div>
  )
}

export default function DealDetailPage() {
  const router = useRouter()
  const params = useParams()
  const id = params?.id as string
  const [deal, setDeal] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('nb_token')
    if (!token) { router.push('/login'); return }
    const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    fetch(`${BASE}/deals/${id}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => {
        if (!r.ok) throw new Error('Not found')
        return r.json()
      })
      .then(d => setDeal(d))
      .catch(() => router.push('/deals'))
      .finally(() => setLoading(false))
  }, [id, router])

  if (loading) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300 }}>
        <span style={{ color: '#64748b' }}>Loading deal...</span>
      </div>
    )
  }

  if (!deal) return null

  const tier = deal.tier || (deal.overall_score >= 75 ? 'S' : deal.overall_score >= 60 ? 'A' : deal.overall_score >= 45 ? 'B' : 'C')
  const ts = TIER_STYLE[tier] || TIER_STYLE.C
  const exitValue = deal.gdv || deal.estimated_value
  const isYieldPlay = !exitValue && (deal.annual_yield || deal.monthly_cashflow)

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      {/* Breadcrumb */}
      <div style={{ marginBottom: 16, fontSize: 13, color: '#475569' }}>
        <Link href="/deals" style={{ color: '#475569', textDecoration: 'none' }}>Deal Pipeline</Link>
        <span style={{ margin: '0 8px' }}>›</span>
        <span style={{ color: '#94a3b8' }}>{deal.title}</span>
      </div>

      {/* Header */}
      <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '20px 24px', marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 16, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 6 }}>
              <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 3, background: 'rgba(37,99,235,0.1)', color: '#60a5fa', fontWeight: 700, textTransform: 'uppercase' }}>
                {deal.strategy.replace('_', ' ')}
              </span>
              <span style={{ fontSize: 11, padding: '3px 8px', borderRadius: 3, background: ts.bg, color: ts.color, fontWeight: 700 }}>
                {ts.label}
              </span>
              <span style={{
                fontSize: 11, padding: '3px 8px', borderRadius: 3, fontWeight: 600,
                background: deal.status === 'active' ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
                color: deal.status === 'active' ? '#10b981' : '#d97706',
                textTransform: 'uppercase'
              }}>
                {deal.status.replace('_', ' ')}
              </span>
            </div>
            <h1 style={{ fontSize: 20, fontWeight: 700, color: '#e2e8f0', marginBottom: 4 }}>{deal.title}</h1>
            <p style={{ fontSize: 13, color: '#64748b' }}>{deal.address} · {deal.postcode} · {deal.council}</p>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 28, fontWeight: 800, color: ts.color }}>{(deal.overall_score || 0).toFixed(0)}</div>
            <div style={{ fontSize: 11, color: '#475569', fontWeight: 600, textTransform: 'uppercase' }}>Overall Score</div>
          </div>
        </div>

        {/* Flag strip */}
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          {deal.is_undervalued && <span style={{ fontSize: 11, padding: '3px 9px', borderRadius: 3, background: 'rgba(16,185,129,0.08)', color: '#10b981', border: '1px solid rgba(16,185,129,0.2)', fontWeight: 600 }}>🔻 Undervalued</span>}
          {deal.is_high_roi && <span style={{ fontSize: 11, padding: '3px 9px', borderRadius: 3, background: 'rgba(239,68,68,0.08)', color: '#f87171', border: '1px solid rgba(239,68,68,0.2)', fontWeight: 600 }}>🚀 High ROI</span>}
          {deal.has_planning_upside && <span style={{ fontSize: 11, padding: '3px 9px', borderRadius: 3, background: 'rgba(245,158,11,0.08)', color: '#fbbf24', border: '1px solid rgba(245,158,11,0.2)', fontWeight: 600 }}>🏗️ Planning Upside</span>}
          {deal.is_distressed && <span style={{ fontSize: 11, padding: '3px 9px', borderRadius: 3, background: 'rgba(245,158,11,0.08)', color: '#d97706', border: '1px solid rgba(245,158,11,0.2)', fontWeight: 600 }}>⚠️ Distressed</span>}
          {deal.near_regen_zone && <span style={{ fontSize: 11, padding: '3px 9px', borderRadius: 3, background: 'rgba(99,102,241,0.08)', color: '#818cf8', border: '1px solid rgba(99,102,241,0.2)', fontWeight: 600 }}>🔄 Regen Zone</span>}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', gap: 16, alignItems: 'start' }}>
        {/* LEFT col */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Financials */}
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '18px 20px' }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Financial Breakdown</h2>

            <Row label="Purchase Price" value={formatPrice(deal.purchase_price)} highlight />
            {deal.refurb_cost && <Row label="Refurbishment Cost" value={formatPrice(deal.refurb_cost)} />}
            {deal.other_costs && <Row label="Other / Acquisition Costs" value={formatPrice(deal.other_costs)} />}
            {deal.total_cost && <Row label="Total Cost (incl. SDLT + legal)" value={<span style={{ color: '#f87171' }}>{formatPrice(deal.total_cost)}</span>} highlight />}

            {exitValue && (
              <>
                <div style={{ margin: '10px 0', borderTop: '1px solid #1e2d45' }} />
                <Row label={deal.gdv ? 'GDV (Gross Development Value)' : 'Estimated ARV / Market Value'} value={<span style={{ color: '#d97706' }}>{formatPrice(exitValue)}</span>} highlight />
                {deal.profit != null && (
                  <Row
                    label="Projected Profit"
                    value={<span style={{ color: deal.profit > 0 ? '#10b981' : '#ef4444', fontWeight: 800, fontSize: 15 }}>{formatPrice(deal.profit)}</span>}
                    highlight
                  />
                )}
                {deal.roi != null && (
                  <Row
                    label="Return on Investment"
                    value={<span style={{ color: deal.roi >= 20 ? '#10b981' : deal.roi >= 10 ? '#d97706' : '#94a3b8', fontWeight: 800, fontSize: 15 }}>{deal.roi.toFixed(1)}%</span>}
                    highlight
                  />
                )}
              </>
            )}

            {isYieldPlay && (
              <>
                <div style={{ margin: '10px 0', borderTop: '1px solid #1e2d45' }} />
                {deal.annual_yield && <Row label="Gross Annual Yield" value={<span style={{ color: '#10b981', fontWeight: 800 }}>{deal.annual_yield}%</span>} highlight />}
                {deal.monthly_cashflow && <Row label="Monthly Cashflow" value={<span style={{ color: '#10b981', fontWeight: 700 }}>£{deal.monthly_cashflow.toLocaleString()}/mo</span>} />}
              </>
            )}
          </div>

          {/* Description */}
          {deal.description && (
            <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '18px 20px' }}>
              <h2 style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 10, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Listing Notes</h2>
              <p style={{ fontSize: 13, color: '#94a3b8', lineHeight: 1.7 }}>{deal.description}</p>
            </div>
          )}

          {/* Property details */}
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '18px 20px' }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Property Details</h2>
            <Row label="Type" value={deal.property_type || '—'} />
            {deal.bedrooms && <Row label="Bedrooms" value={deal.bedrooms} />}
            <Row label="Council" value={deal.council || '—'} />
            <Row label="Postcode" value={deal.postcode || '—'} />
            <Row label="Status" value={deal.status?.replace('_', ' ').toUpperCase() || '—'} />
            {deal.source_url && (
              <div style={{ marginTop: 12 }}>
                <a href={deal.source_url} target="_blank" rel="noopener noreferrer"
                  style={{ fontSize: 12, color: '#3b82f6', textDecoration: 'none' }}>
                  View original listing →
                </a>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT col — scoring */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Score breakdown */}
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '18px 20px' }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 16, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Score Breakdown</h2>

            {/* Overall ring */}
            <div style={{ textAlign: 'center', marginBottom: 20 }}>
              <div style={{ display: 'inline-flex', flexDirection: 'column', alignItems: 'center', background: ts.bg, borderRadius: 8, padding: '16px 28px', border: `1px solid ${ts.color}22` }}>
                <div style={{ fontSize: 42, fontWeight: 900, color: ts.color, lineHeight: 1 }}>{(deal.overall_score || 0).toFixed(0)}</div>
                <div style={{ fontSize: 10, color: ts.color, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.8px', marginTop: 4 }}>{tier}-Tier</div>
              </div>
            </div>

            <ScoreBar label="ROI Score (35% weight)" value={deal.roi_score || 0} color="#10b981" />
            <ScoreBar label="Market / BMV Score (30%)" value={deal.market_score || 0} color="#3b82f6" />
            <ScoreBar label="Planning Uplift (20%)" value={deal.planning_uplift_score || 0} color="#f59e0b" />
            <ScoreBar label="Risk Score (lower = better)" value={deal.risk_score || 0} color="#ef4444" />
          </div>

          {/* Score drivers */}
          {deal.score_drivers && deal.score_drivers.length > 0 && (
            <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '18px 20px' }}>
              <h2 style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 14, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Score Drivers</h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {deal.score_drivers.map((d: any, i: number) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 10px', background: '#0a1020', borderRadius: 4 }}>
                    <span style={{ fontSize: 16, flexShrink: 0 }}>{d.icon}</span>
                    <span style={{ fontSize: 12, color: '#94a3b8', lineHeight: 1.5 }}>{d.label}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strategy guide */}
          <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '18px 20px' }}>
            <h2 style={{ fontSize: 13, fontWeight: 700, color: '#e2e8f0', marginBottom: 12, textTransform: 'uppercase', letterSpacing: '0.5px' }}>Strategy Profile</h2>
            <StrategyGuide strategy={deal.strategy} />
          </div>
        </div>
      </div>

      {/* Back link */}
      <div style={{ marginTop: 24 }}>
        <Link href="/deals" style={{ fontSize: 13, color: '#475569', textDecoration: 'none' }}>← Back to Deal Pipeline</Link>
      </div>
    </div>
  )
}

function StrategyGuide({ strategy }: { strategy: string }) {
  const guides: Record<string, { title: string; steps: string[]; risk: string; timeline: string }> = {
    flip: {
      title: 'Buy, Refurb, Sell',
      steps: ['Source BMV', 'Refurbish to market standard', 'Sell at ARV within 3–6 months'],
      risk: 'Medium', timeline: '3–9 months',
    },
    brrr: {
      title: 'Buy, Refurb, Refinance, Rent',
      steps: ['Buy below market', 'Full refurb to uplift value', 'Refinance to pull capital back out', 'Let property for long-term income'],
      risk: 'Medium', timeline: '6–12 months to refinance',
    },
    brr: {
      title: 'Buy, Refurb, Rent',
      steps: ['Buy below market', 'Refurbish to rental standard', 'Let to tenants for income'],
      risk: 'Low–Medium', timeline: 'Ongoing',
    },
    hmo: {
      title: 'House in Multiple Occupation',
      steps: ['Acquire suitable property (3+ beds)', 'Apply for HMO licence', 'Let rooms individually for premium yield'],
      risk: 'Medium', timeline: 'Ongoing',
    },
    btl: {
      title: 'Buy to Let',
      steps: ['Acquire investment property', 'Let to single household', 'Manage for long-term yield'],
      risk: 'Low', timeline: 'Ongoing',
    },
    conversion: {
      title: 'Commercial to Residential',
      steps: ['Acquire commercial unit', 'Obtain prior approval / change of use', 'Convert to residential units', 'Sell or retain for income'],
      risk: 'High', timeline: '12–24 months',
    },
    planning_uplift: {
      title: 'Planning Gain Strategy',
      steps: ['Acquire at existing use value', 'Obtain planning permission', 'Sell with planning consent or develop'],
      risk: 'High', timeline: '12–36 months',
    },
    auction: {
      title: 'Auction Purchase',
      steps: ['Research lot pre-auction', 'Finance arranged in advance', 'Bid to guide price + 15%', 'Complete within 28 days'],
      risk: 'Medium–High', timeline: '28-day completion',
    },
  }

  const g = guides[strategy] || guides.flip
  return (
    <div>
      <div style={{ fontSize: 13, fontWeight: 600, color: '#e2e8f0', marginBottom: 8 }}>{g.title}</div>
      <div style={{ display: 'flex', gap: 16, marginBottom: 10 }}>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: '#475569' }}>Risk: </span>
          <span style={{ color: '#d97706', fontWeight: 600 }}>{g.risk}</span>
        </div>
        <div style={{ fontSize: 11 }}>
          <span style={{ color: '#475569' }}>Timeline: </span>
          <span style={{ color: '#94a3b8', fontWeight: 600 }}>{g.timeline}</span>
        </div>
      </div>
      <ol style={{ paddingLeft: 16, margin: 0 }}>
        {g.steps.map((s, i) => (
          <li key={i} style={{ fontSize: 12, color: '#64748b', marginBottom: 5, lineHeight: 1.5 }}>{s}</li>
        ))}
      </ol>
    </div>
  )
}
