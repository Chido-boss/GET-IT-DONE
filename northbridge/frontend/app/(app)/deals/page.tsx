'use client'

import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { formatPrice } from '@/lib/utils'

const STRATEGIES = ['flip', 'brrr', 'brr', 'hmo', 'btl', 'conversion', 'planning_uplift', 'auction']
const FLAGS = [
  { key: 'is_undervalued', label: 'Undervalued' },
  { key: 'is_high_roi', label: 'High ROI' },
  { key: 'has_planning_upside', label: 'Planning Upside' },
]

const TIER_STYLE: Record<string, { bg: string; color: string }> = {
  S: { bg: 'rgba(16,185,129,0.12)', color: '#10b981' },
  A: { bg: 'rgba(245,158,11,0.12)', color: '#d97706' },
  B: { bg: 'rgba(37,99,235,0.12)', color: '#3b82f6' },
  C: { bg: 'rgba(100,116,139,0.1)', color: '#64748b' },
}

export default function DealsPage() {
  const router = useRouter()
  const [deals, setDeals] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    strategy: '', min_roi: '', max_price: '', min_price: '',
    council: '', min_score: '', flag: '', sort: 'score',
  })
  const [page, setPage] = useState(1)

  const load = useCallback(async () => {
    const token = localStorage.getItem('nb_token')
    if (!token) { router.push('/login'); return }
    setLoading(true)
    const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const params = new URLSearchParams({ limit: '50', offset: String((page - 1) * 50), sort: filters.sort })
    if (filters.strategy) params.set('strategy', filters.strategy)
    if (filters.min_roi) params.set('min_roi', filters.min_roi)
    if (filters.max_price) params.set('max_price', filters.max_price)
    if (filters.min_price) params.set('min_price', filters.min_price)
    if (filters.council) params.set('council', filters.council)
    if (filters.min_score) params.set('min_score', filters.min_score)
    if (filters.flag) params.set(filters.flag, 'true')
    try {
      const res = await fetch(`${BASE}/deals?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      const data = await res.json()
      setDeals(data.items || [])
      setTotal(data.total || 0)
    } finally {
      setLoading(false)
    }
  }, [filters, page, router])

  useEffect(() => { load() }, [load])

  const setFilter = (key: string, value: string) => {
    setFilters(f => ({ ...f, [key]: value }))
    setPage(1)
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>Deal Pipeline</h1>
        <p style={{ color: '#64748b', fontSize: 14, marginTop: 4 }}>{total} deals · scored and ranked</p>
      </div>

      {/* Filter bar */}
      <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: '14px 16px', marginBottom: 16, display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Strategy</div>
          <select value={filters.strategy} onChange={e => setFilter('strategy', e.target.value)}
            style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13 }}>
            <option value="">All strategies</option>
            {STRATEGIES.map(s => <option key={s} value={s}>{s.replace('_', ' ').toUpperCase()}</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Min ROI %</div>
          <input type="number" value={filters.min_roi} onChange={e => setFilter('min_roi', e.target.value)}
            placeholder="e.g. 15" style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13, width: 80 }} />
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Max Price</div>
          <input type="number" value={filters.max_price} onChange={e => setFilter('max_price', e.target.value)}
            placeholder="e.g. 150000" style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13, width: 100 }} />
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Flag</div>
          <select value={filters.flag} onChange={e => setFilter('flag', e.target.value)}
            style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13 }}>
            <option value="">Any</option>
            {FLAGS.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Min Score</div>
          <select value={filters.min_score} onChange={e => setFilter('min_score', e.target.value)}
            style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13 }}>
            <option value="">Any</option>
            <option value="45">45+</option>
            <option value="60">60+</option>
            <option value="75">75+</option>
          </select>
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Sort</div>
          <select value={filters.sort} onChange={e => setFilter('sort', e.target.value)}
            style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13 }}>
            <option value="score">Score</option>
            <option value="roi">ROI</option>
            <option value="price">Price ↑</option>
            <option value="created">Newest</option>
          </select>
        </div>
        <button onClick={() => { setFilters({ strategy: '', min_roi: '', max_price: '', min_price: '', council: '', min_score: '', flag: '', sort: 'score' }); setPage(1) }}
          style={{ padding: '7px 14px', background: 'transparent', border: '1px solid #1e2d45', color: '#64748b', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}>
          Reset
        </button>
      </div>

      {/* Table */}
      <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1e2d45' }}>
              {['#', 'Property', 'Strategy', 'Purchase', 'GDV / ARV', 'Profit', 'ROI', 'Score', 'Flags', ''].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 12px', fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={10} style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading...</td></tr>
            ) : deals.length === 0 ? (
              <tr><td colSpan={10} style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                No deals found. Run <code>python scripts/seed_deals.py</code> to populate.
              </td></tr>
            ) : deals.map((deal, i) => {
              const tier = deal.tier || 'C'
              const ts = TIER_STYLE[tier] || TIER_STYLE.C
              return (
                <tr key={deal.id} style={{ borderBottom: '1px solid #0f1729' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#162035')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <td style={{ padding: '11px 12px', color: '#64748b', fontWeight: 600 }}>{deal.rank || i + 1}</td>
                  <td style={{ padding: '11px 12px', maxWidth: 200 }}>
                    <div style={{ color: '#e2e8f0', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{deal.title}</div>
                    <div style={{ color: '#64748b', fontSize: 11, marginTop: 2 }}>{deal.postcode} · {deal.council}</div>
                  </td>
                  <td style={{ padding: '11px 12px' }}>
                    <span style={{ fontSize: 11, padding: '3px 7px', borderRadius: 3, background: 'rgba(37,99,235,0.1)', color: '#60a5fa', fontWeight: 600, textTransform: 'uppercase' }}>
                      {deal.strategy.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={{ padding: '11px 12px', color: '#e2e8f0', fontWeight: 600 }}>{formatPrice(deal.purchase_price)}</td>
                  <td style={{ padding: '11px 12px', color: '#d97706' }}>{deal.gdv || deal.estimated_value ? formatPrice(deal.gdv || deal.estimated_value) : '—'}</td>
                  <td style={{ padding: '11px 12px', color: deal.profit && deal.profit > 0 ? '#10b981' : '#ef4444' }}>
                    {deal.profit ? formatPrice(deal.profit) : deal.monthly_cashflow ? `£${deal.monthly_cashflow}/mo` : '—'}
                  </td>
                  <td style={{ padding: '11px 12px', color: deal.roi && deal.roi >= 20 ? '#10b981' : deal.roi && deal.roi >= 10 ? '#d97706' : '#94a3b8', fontWeight: 700 }}>
                    {deal.roi ? `${deal.roi.toFixed(0)}%` : deal.annual_yield ? `${deal.annual_yield}% yield` : '—'}
                  </td>
                  <td style={{ padding: '11px 12px' }}>
                    <span style={{ fontSize: 12, fontWeight: 800, padding: '3px 8px', borderRadius: 3, background: ts.bg, color: ts.color }}>
                      {tier} · {(deal.overall_score || 0).toFixed(0)}
                    </span>
                  </td>
                  <td style={{ padding: '11px 12px' }}>
                    <div style={{ display: 'flex', gap: 3 }}>
                      {deal.is_undervalued && <span title="Undervalued" style={{ fontSize: 14 }}>🔻</span>}
                      {deal.is_high_roi && <span title="High ROI" style={{ fontSize: 14 }}>🚀</span>}
                      {deal.has_planning_upside && <span title="Planning upside" style={{ fontSize: 14 }}>🏗️</span>}
                      {deal.is_distressed && <span title="Distressed" style={{ fontSize: 14 }}>⚠️</span>}
                      {deal.near_regen_zone && <span title="Near regen zone" style={{ fontSize: 14 }}>🔄</span>}
                    </div>
                  </td>
                  <td style={{ padding: '11px 12px' }}>
                    <Link href={`/deals/${deal.id}`} style={{ fontSize: 12, padding: '4px 10px', borderRadius: 4, background: '#162035', color: '#94a3b8', textDecoration: 'none' }}>
                      View →
                    </Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {total > 50 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            style={{ padding: '6px 14px', background: '#0f1729', border: '1px solid #1e2d45', color: '#94a3b8', borderRadius: 4, cursor: 'pointer' }}>← Prev</button>
          <span style={{ padding: '6px 14px', color: '#64748b', fontSize: 13 }}>Page {page} of {Math.ceil(total / 50)}</span>
          <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 50)}
            style={{ padding: '6px 14px', background: '#0f1729', border: '1px solid #1e2d45', color: '#94a3b8', borderRadius: 4, cursor: 'pointer' }}>Next →</button>
        </div>
      )}
    </div>
  )
}
