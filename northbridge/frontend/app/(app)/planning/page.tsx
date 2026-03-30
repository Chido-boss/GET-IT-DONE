'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { api } from '@/lib/api'
import { relativeDate } from '@/lib/utils'
import type { PlanningApplication } from '@/types'

const COUNCILS = [
  'Gateshead', 'Newcastle', 'Sunderland', 'Durham',
  'South Tyneside', 'North Tyneside', 'Middlesbrough',
  'Stockton', 'Darlington', 'Northumberland'
]

const UPLIFT_SIGNALS: Record<string, { label: string; color: string }> = {
  'change_of_use': { label: 'Change of Use', color: 'rgba(139,92,246,0.15)' },
  'conversion': { label: 'Conversion', color: 'rgba(139,92,246,0.15)' },
  'prior_approval': { label: 'Prior Approval', color: 'rgba(245,158,11,0.15)' },
  'residential': { label: 'Residential', color: 'rgba(16,185,129,0.15)' },
  'commercial_to_resi': { label: 'Comm→Resi', color: 'rgba(245,158,11,0.15)' },
  'new_build': { label: 'New Build', color: 'rgba(37,99,235,0.15)' },
  'regeneration': { label: 'Regeneration', color: 'rgba(16,185,129,0.15)' },
}

export default function PlanningPage() {
  const router = useRouter()
  const [apps, setApps] = useState<PlanningApplication[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ council: '', min_score: '', keyword: '', application_type: '' })
  const [page, setPage] = useState(1)

  useEffect(() => {
    const token = localStorage.getItem('nb_token')
    if (!token) { router.push('/login'); return }
    load()
  }, [filters, page])

  async function load() {
    setLoading(true)
    try {
      const params: Record<string, string> = { limit: '50', offset: String((page - 1) * 50) }
      if (filters.council) params.council = filters.council
      if (filters.min_score) params.uplift_score_min = filters.min_score
      if (filters.keyword) params.keyword = filters.keyword
      if (filters.application_type) params.application_type = filters.application_type
      const data = await api.planning.list(params)
      setApps(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }

  function scoreColor(score: number) {
    if (score >= 60) return '#10b981'
    if (score >= 35) return '#d97706'
    return '#475569'
  }

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>Planning Intelligence</h1>
        <p style={{ color: '#64748b', fontSize: 14, marginTop: 4 }}>
          {total} applications tracked across 10 North East councils — scored for investment uplift
        </p>
      </div>

      {/* Filters */}
      <div style={{
        background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6,
        padding: '14px 16px', marginBottom: 16,
        display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end'
      }}>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Council</div>
          <select
            value={filters.council}
            onChange={e => { setFilters(f => ({ ...f, council: e.target.value })); setPage(1) }}
            style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13 }}
          >
            <option value="">All councils</option>
            {COUNCILS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Min Uplift Score</div>
          <select
            value={filters.min_score}
            onChange={e => { setFilters(f => ({ ...f, min_score: e.target.value })); setPage(1) }}
            style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13 }}
          >
            <option value="">Any</option>
            <option value="25">25+ Moderate</option>
            <option value="40">40+ Worth watching</option>
            <option value="60">60+ High signal</option>
            <option value="80">80+ Strong</option>
          </select>
        </div>
        <div>
          <div style={{ fontSize: 11, color: '#64748b', marginBottom: 4 }}>Keyword</div>
          <input
            value={filters.keyword}
            onChange={e => { setFilters(f => ({ ...f, keyword: e.target.value })); setPage(1) }}
            placeholder="e.g. conversion, change of use"
            style={{ background: '#162035', border: '1px solid #1e2d45', color: '#e2e8f0', padding: '7px 10px', borderRadius: 4, fontSize: 13, width: 200 }}
          />
        </div>
        <button
          onClick={() => { setFilters({ council: '', min_score: '', keyword: '', application_type: '' }); setPage(1) }}
          style={{ padding: '7px 14px', background: 'transparent', border: '1px solid #1e2d45', color: '#64748b', borderRadius: 4, cursor: 'pointer', fontSize: 13 }}
        >
          Reset
        </button>
      </div>

      {/* Table */}
      <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #1e2d45' }}>
              {['Reference', 'Address', 'Council', 'Proposal', 'Signals', 'Uplift', 'Date', 'Status'].map(h => (
                <th key={h} style={{ textAlign: 'left', padding: '10px 12px', fontSize: 11, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 600 }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={8} style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>Loading...</td></tr>
            ) : apps.length === 0 ? (
              <tr><td colSpan={8} style={{ padding: 40, textAlign: 'center', color: '#64748b' }}>
                No planning applications found. Upload data via Admin → Import.
              </td></tr>
            ) : apps.map(app => (
              <tr key={app.id} style={{ borderBottom: '1px solid #0f1729' }}
                onMouseEnter={e => (e.currentTarget.style.background = '#162035')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <td style={{ padding: '10px 12px', color: '#64748b' }}>
                  {app.url ? (
                    <a href={app.url} target="_blank" rel="noreferrer" style={{ color: '#3b82f6', textDecoration: 'none' }}>
                      {app.application_reference}
                    </a>
                  ) : app.application_reference}
                </td>
                <td style={{ padding: '10px 12px', maxWidth: 180 }}>
                  <div style={{ color: '#e2e8f0', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {app.address}
                  </div>
                  {app.postcode && <div style={{ color: '#64748b', fontSize: 11 }}>{app.postcode}</div>}
                </td>
                <td style={{ padding: '10px 12px', color: '#94a3b8' }}>{app.council?.replace(' Council', '')}</td>
                <td style={{ padding: '10px 12px', maxWidth: 220 }}>
                  <div style={{ color: '#94a3b8', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {app.proposal || app.application_type || '—'}
                  </div>
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                    {(app.uplift_signals || []).slice(0, 2).map((sig, i) => (
                      <span key={i} style={{
                        fontSize: 10, padding: '2px 6px', borderRadius: 3, fontWeight: 600,
                        background: 'rgba(139,92,246,0.12)', color: '#a78bfa'
                      }}>{sig}</span>
                    ))}
                  </div>
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <span style={{
                    fontSize: 12, fontWeight: 700, padding: '2px 8px', borderRadius: 3,
                    background: `${scoreColor(app.uplift_score)}20`,
                    color: scoreColor(app.uplift_score)
                  }}>
                    {Math.round(app.uplift_score)}
                  </span>
                </td>
                <td style={{ padding: '10px 12px', color: '#64748b', whiteSpace: 'nowrap' }}>
                  {app.date_received ? relativeDate(app.date_received) : '—'}
                </td>
                <td style={{ padding: '10px 12px' }}>
                  <span style={{
                    fontSize: 11, padding: '2px 7px', borderRadius: 3,
                    background: app.status === 'Approved' ? 'rgba(16,185,129,0.1)' : 'rgba(100,116,139,0.1)',
                    color: app.status === 'Approved' ? '#10b981' : '#94a3b8'
                  }}>
                    {app.status || 'Pending'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {total > 50 && (
        <div style={{ display: 'flex', justifyContent: 'center', gap: 8, marginTop: 16 }}>
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            style={{ padding: '6px 14px', background: '#0f1729', border: '1px solid #1e2d45', color: '#94a3b8', borderRadius: 4, cursor: 'pointer' }}>
            ← Prev
          </button>
          <span style={{ padding: '6px 14px', color: '#64748b', fontSize: 13 }}>
            Page {page} of {Math.ceil(total / 50)}
          </span>
          <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(total / 50)}
            style={{ padding: '6px 14px', background: '#0f1729', border: '1px solid #1e2d45', color: '#94a3b8', borderRadius: 4, cursor: 'pointer' }}>
            Next →
          </button>
        </div>
      )}
    </div>
  )
}
