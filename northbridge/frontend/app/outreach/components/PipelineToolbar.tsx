'use client'

import type { PipelineFilters, DealSource, DealStrategy, Tier, OutreachStage } from '../types'

const BG = '#070d1a'
const SURFACE = '#0c1524'
const SURFACE2 = '#101e34'
const BORDER = '#162038'
const TEXT = '#dde6f4'
const TEXT_MUTED = '#546278'
const TEXT_DIM = '#2e3f55'
const ACCENT = '#1d4ed8'
const ACCENT_LIGHT = '#3b82f6'
const GOLD = '#c48f2a'
const GOLD_LIGHT = '#d4a94a'
const GREEN = '#10b981'
const AMBER = '#f59e0b'

const STAGE_COLORS: Record<string, string> = {
  new: TEXT_MUTED,
  contacted: ACCENT_LIGHT,
  buyer_sent: GOLD,
  follow_up: AMBER,
  fee_locked: GREEN,
  passed: TEXT_DIM,
}

const STAGE_LABELS: Record<string, string> = {
  new: 'New',
  contacted: 'Contacted',
  buyer_sent: 'Buyer Sent',
  follow_up: 'Follow Up',
  fee_locked: 'Fee Locked',
  passed: 'Passed',
}

const SOURCES: DealSource[] = ['Rightmove', 'Auction', 'OTM', 'Off-market', 'Direct']
const STRATEGIES: { value: DealStrategy; label: string }[] = [
  { value: 'flip', label: 'Flip' },
  { value: 'light_refurb', label: 'Light Refurb' },
  { value: 'brrr', label: 'BRRR' },
  { value: 'btl', label: 'BTL' },
  { value: 'income_hold', label: 'Income Hold' },
  { value: 'hmo', label: 'HMO' },
  { value: 'conversion', label: 'Conversion' },
  { value: 'auction', label: 'Auction' },
]

interface Props {
  filters: PipelineFilters
  setFilters: (f: PipelineFilters) => void
  stats: {
    stageCounts: Record<string, number>
    avgScore: string
    sTier: number
    potentialRevenue: number
  }
  totalDeals: number
  filteredCount: number
  onExportCSV: () => void
}

export function PipelineToolbar({ filters, setFilters, stats, totalDeals, filteredCount, onExportCSV }: Props) {
  const set = (key: keyof PipelineFilters, value: any) => setFilters({ ...filters, [key]: value })
  const reset = () => setFilters({ search: '', source: '', strategy: '', min_score: '', tier: '', stage: '' })

  const inputSx: React.CSSProperties = {
    background: SURFACE2, border: `1px solid ${BORDER}`, color: TEXT,
    padding: '6px 9px', borderRadius: 4, fontSize: 12, outline: 'none',
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* ── Stats strip ─────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', gap: 1, background: BORDER, borderRadius: 5, overflow: 'hidden',
      }}>
        {[
          { label: 'Total', value: totalDeals.toString(), color: TEXT },
          { label: 'Avg Score', value: stats.avgScore, color: ACCENT_LIGHT },
          { label: 'S-Tier', value: stats.sTier.toString(), color: GREEN },
          ...Object.entries(STAGE_LABELS).map(([key, label]) => ({
            label,
            value: (stats.stageCounts[key] || 0).toString(),
            color: STAGE_COLORS[key],
          })),
          {
            label: 'Est. Revenue',
            value: stats.potentialRevenue > 0 ? `£${stats.potentialRevenue.toLocaleString()}` : '£0',
            color: GOLD_LIGHT,
          },
        ].map(item => (
          <div key={item.label} style={{
            flex: 1, background: SURFACE, padding: '8px 10px', textAlign: 'center',
            minWidth: 0,
          }}>
            <div style={{ fontSize: 9, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 3 }}>
              {item.label}
            </div>
            <div style={{ fontSize: 15, fontWeight: 700, color: item.color, fontVariantNumeric: 'tabular-nums' }}>
              {item.value}
            </div>
          </div>
        ))}
      </div>

      {/* ── Controls row ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'flex-end' }}>

        {/* Search */}
        <div style={{ flex: '1 1 180px', minWidth: 0 }}>
          <input
            value={filters.search}
            onChange={e => set('search', e.target.value)}
            placeholder="Search address, postcode, council…"
            style={{ ...inputSx, width: '100%', boxSizing: 'border-box' }}
          />
        </div>

        {/* Source pills */}
        <div style={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
          {SOURCES.map(src => (
            <button
              key={src}
              onClick={() => set('source', filters.source === src ? '' : src)}
              style={{
                padding: '5px 9px', borderRadius: 3, fontSize: 11, fontWeight: 600,
                border: filters.source === src ? `1px solid ${ACCENT}` : `1px solid ${BORDER}`,
                background: filters.source === src ? `${ACCENT}20` : 'transparent',
                color: filters.source === src ? ACCENT_LIGHT : TEXT_MUTED,
                cursor: 'pointer', whiteSpace: 'nowrap',
              }}
            >
              {src}
            </button>
          ))}
        </div>

        {/* Strategy */}
        <select value={filters.strategy} onChange={e => set('strategy', e.target.value as any)} style={inputSx}>
          <option value="">All strategies</option>
          {STRATEGIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>

        {/* Stage */}
        <select value={filters.stage} onChange={e => set('stage', e.target.value as any)} style={inputSx}>
          <option value="">All stages</option>
          {Object.entries(STAGE_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select>

        {/* Tier */}
        <select value={filters.tier} onChange={e => set('tier', e.target.value as any)} style={inputSx}>
          <option value="">All tiers</option>
          {(['S', 'A', 'B', 'C'] as Tier[]).map(t => <option key={t} value={t}>Tier {t}</option>)}
        </select>

        {/* Min score */}
        <select value={filters.min_score} onChange={e => set('min_score', e.target.value === '' ? '' : Number(e.target.value))} style={inputSx}>
          <option value="">Any score</option>
          <option value={60}>60+</option>
          <option value={70}>70+</option>
          <option value={80}>80+</option>
        </select>

        {/* Actions */}
        <button onClick={reset} style={{
          padding: '6px 11px', background: 'transparent', border: `1px solid ${BORDER}`,
          borderRadius: 4, color: TEXT_DIM, fontSize: 11, cursor: 'pointer',
        }}>
          Reset
        </button>

        <button onClick={onExportCSV} style={{
          padding: '6px 11px', background: 'transparent', border: `1px solid ${BORDER}`,
          borderRadius: 4, color: TEXT_MUTED, fontSize: 11, fontWeight: 600, cursor: 'pointer',
        }}>
          Export CSV
        </button>

        {/* Showing count */}
        <div style={{ fontSize: 11, color: TEXT_DIM, alignSelf: 'center', whiteSpace: 'nowrap' }}>
          {filteredCount} of {totalDeals}
        </div>
      </div>
    </div>
  )
}
