'use client'

import { useEffect, useState, useCallback, useMemo } from 'react'
import { useRouter } from 'next/navigation'
import type { Deal, DealsResponse } from '@/types'

// ── Formatting helpers ────────────────────────────────────────────────────────

function fmt(n: number | null | undefined): string {
  if (n == null) return '—'
  return `£${n.toLocaleString('en-GB')}`
}

function fmtPct(n: number | null | undefined, dp = 0): string {
  if (n == null) return '—'
  return `${n.toFixed(dp)}%`
}

function strategyLabel(s: string): string {
  const map: Record<string, string> = {
    flip: 'Flip',
    light_refurb_flip: 'Light Refurb',
    brrr: 'BRRR',
    brr: 'BRR',
    btl: 'BTL',
    income_hold: 'Income Hold',
    hmo: 'HMO',
    conversion: 'Conversion',
    planning_uplift: 'Planning',
    auction: 'Auction',
  }
  return map[s] || s.replace(/_/g, ' ')
}

// ── Theme constants ───────────────────────────────────────────────────────────

const BG = '#090e1a'
const SURFACE = '#0d1626'
const SURFACE2 = '#111c30'
const BORDER = '#1a2540'
const BORDER2 = '#243050'
const TEXT = '#dde6f4'
const TEXT_MUTED = '#5a6e8a'
const TEXT_DIM = '#38495e'
const ACCENT = '#1d4ed8'
const ACCENT_LIGHT = '#3b82f6'
const GOLD = '#c48f2a'
const GOLD_LIGHT = '#d4a94a'
const GREEN = '#10b981'
const RED = '#ef4444'
const AMBER = '#f59e0b'

const TIER_CONFIG: Record<string, { bg: string; border: string; color: string; label: string }> = {
  S: { bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.3)', color: '#10b981', label: 'S-Tier' },
  A: { bg: 'rgba(196,143,42,0.08)', border: 'rgba(196,143,42,0.3)', color: '#c48f2a', label: 'A-Tier' },
  B: { bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.3)', color: '#3b82f6', label: 'B-Tier' },
  C: { bg: 'rgba(90,110,138,0.07)', border: 'rgba(90,110,138,0.2)', color: '#5a6e8a', label: 'C-Tier' },
}

const STRATEGY_COLORS: Record<string, string> = {
  flip: '#8b5cf6',
  light_refurb_flip: '#7c3aed',
  brrr: '#2563eb',
  brr: '#3b82f6',
  btl: '#0891b2',
  income_hold: '#0e7490',
  hmo: '#0f766e',
  conversion: '#b45309',
  planning_uplift: '#92400e',
  auction: '#dc2626',
}

const RISK_CONFIG: Record<string, { color: string; bg: string }> = {
  Low: { color: GREEN, bg: 'rgba(16,185,129,0.08)' },
  Medium: { color: AMBER, bg: 'rgba(245,158,11,0.08)' },
  High: { color: RED, bg: 'rgba(239,68,68,0.08)' },
}

const CONF_CONFIG: Record<string, { color: string }> = {
  High: { color: GREEN },
  Medium: { color: AMBER },
  Low: { color: TEXT_MUTED },
}

const STRATEGIES = [
  'flip', 'light_refurb_flip', 'brrr', 'btl', 'income_hold', 'hmo', 'conversion', 'planning_uplift', 'auction',
]

// ── Sub-components ────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: string }) {
  const accentColor = accent === 'green' ? GREEN : accent === 'gold' ? GOLD : accent === 'blue' ? ACCENT_LIGHT : TEXT_MUTED
  return (
    <div style={{
      background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 6, padding: '16px 18px',
    }}>
      <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase', color: TEXT_DIM, marginBottom: 8 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: accentColor, fontVariantNumeric: 'tabular-nums', letterSpacing: '-0.02em', lineHeight: 1 }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: TEXT_MUTED, marginTop: 5 }}>{sub}</div>}
    </div>
  )
}

function TierBadge({ tier, score }: { tier: string | null; score: number | null }) {
  const t = tier || 'C'
  const cfg = TIER_CONFIG[t] || TIER_CONFIG.C
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: cfg.bg, border: `1px solid ${cfg.border}`, color: cfg.color,
      fontSize: 11, fontWeight: 800, letterSpacing: '0.04em',
      padding: '3px 8px', borderRadius: 4, whiteSpace: 'nowrap',
    }}>
      {t} · {score != null ? score.toFixed(0) : '—'}
    </span>
  )
}

function StrategyTag({ strategy }: { strategy: string }) {
  const color = STRATEGY_COLORS[strategy] || ACCENT_LIGHT
  return (
    <span style={{
      fontSize: 11, fontWeight: 600, padding: '2px 7px', borderRadius: 3,
      background: `${color}15`, color, border: `1px solid ${color}28`,
      textTransform: 'uppercase' as const, letterSpacing: '0.04em', whiteSpace: 'nowrap',
    }}>
      {strategyLabel(strategy)}
    </span>
  )
}

function ScoreBar({ value, color }: { value: number | null; color: string }) {
  const pct = value ?? 0
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ flex: 1, height: 4, background: BORDER2, borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontSize: 11, color: TEXT_MUTED, fontVariantNumeric: 'tabular-nums', minWidth: 24, textAlign: 'right' }}>
        {pct.toFixed(0)}
      </span>
    </div>
  )
}

function LockOverlay({ tier }: { tier: 'analyst' | 'investor' }) {
  return (
    <div style={{
      position: 'relative', overflow: 'hidden', borderRadius: 4,
    }}>
      <div style={{
        filter: 'blur(4px)', opacity: 0.35, pointerEvents: 'none', userSelect: 'none',
        padding: '8px 0',
      }}>
        <div style={{ height: 12, background: BORDER2, borderRadius: 2, marginBottom: 6, width: '80%' }} />
        <div style={{ height: 12, background: BORDER2, borderRadius: 2, marginBottom: 6, width: '60%' }} />
        <div style={{ height: 12, background: BORDER2, borderRadius: 2, width: '70%' }} />
      </div>
      <div style={{
        position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 4,
      }}>
        <span style={{ fontSize: 14, color: TEXT_DIM }}>🔒</span>
        <span style={{ fontSize: 11, color: TEXT_DIM, fontWeight: 600 }}>
          {tier === 'analyst' ? 'Analyst' : 'Investor'} tier required
        </span>
      </div>
    </div>
  )
}

// ── Detail Panel ─────────────────────────────────────────────────────────────

function DetailPanel({ deal, onClose }: { deal: Deal; onClose: () => void }) {
  const tier = deal.tier || 'C'
  const cfg = TIER_CONFIG[tier]
  const roi = deal.roi_pct ?? deal.roi
  const annualYield = deal.annual_yield_pct ?? deal.annual_yield
  const netProfit = deal.net_profit ?? deal.profit
  const risk = deal.risk_level || 'Medium'
  const riskCfg = RISK_CONFIG[risk] || RISK_CONFIG.Medium
  const confCfg = CONF_CONFIG[deal.confidence || 'Medium'] || CONF_CONFIG.Medium

  return (
    <div style={{
      width: 360, minWidth: 360, background: SURFACE, borderLeft: `1px solid ${BORDER}`,
      display: 'flex', flexDirection: 'column', height: '100%', overflowY: 'auto',
    }}>
      {/* Header */}
      <div style={{ padding: '16px 18px', borderBottom: `1px solid ${BORDER}`, background: SURFACE2 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <TierBadge tier={tier} score={deal.overall_score} />
              {deal.confidence && (
                <span style={{ fontSize: 11, color: confCfg.color, fontWeight: 600 }}>
                  {deal.confidence} Confidence
                </span>
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: TEXT, lineHeight: 1.4 }}>
              {deal.address}
            </div>
            <div style={{ fontSize: 11, color: TEXT_MUTED, marginTop: 3 }}>
              {deal.postcode} · {deal.council}
              {deal.bedrooms && ` · ${deal.bedrooms} bed`}
              {deal.property_type && ` ${deal.property_type}`}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: TEXT_MUTED, cursor: 'pointer',
            fontSize: 18, lineHeight: 1, padding: 2, flexShrink: 0,
          }}>×</button>
        </div>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 18px' }}>

        {/* Tags */}
        {deal.tags && deal.tags.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 14 }}>
            {deal.tags.map(tag => (
              <span key={tag} style={{
                fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 3,
                background: `${ACCENT}18`, color: ACCENT_LIGHT, border: `1px solid ${ACCENT}28`,
                letterSpacing: '0.03em', textTransform: 'uppercase' as const,
              }}>{tag}</span>
            ))}
          </div>
        )}

        {/* Strategy + Source */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <StrategyTag strategy={deal.strategy} />
          {deal.source && (
            <span style={{ fontSize: 11, color: TEXT_MUTED }}>via {deal.source}</span>
          )}
          {deal.days_on_market != null && (
            <span style={{ fontSize: 11, color: TEXT_MUTED }}>{deal.days_on_market}d on market</span>
          )}
        </div>

        {/* Summary */}
        {deal.summary && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>
              Investment Thesis
            </div>
            <div style={{ fontSize: 12.5, color: '#94a3b8', lineHeight: 1.6 }}>
              {deal.summary}
            </div>
          </div>
        )}

        {/* Key Numbers */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
            Key Numbers
          </div>
          <div style={{ background: SURFACE2, border: `1px solid ${BORDER}`, borderRadius: 5, overflow: 'hidden' }}>
            {[
              { label: 'Asking Price', value: fmt(deal.purchase_price), color: TEXT },
              { label: 'Est. Market Value', value: deal.estimated_value ? fmt(deal.estimated_value) : deal.gdv ? fmt(deal.gdv) : '—', color: TEXT },
              { label: 'Discount to Market', value: fmtPct(deal.discount_pct, 1), color: deal.discount_pct && deal.discount_pct >= 15 ? GREEN : deal.discount_pct && deal.discount_pct >= 8 ? GOLD : TEXT_MUTED },
              { label: 'Refurb Cost', value: fmt(deal.refurb_cost), color: TEXT_MUTED },
              { label: 'Total Cost In', value: fmt(deal.total_cost), color: TEXT },
              deal.gdv || deal.estimated_value
                ? { label: 'Gross Profit', value: fmt(deal.gross_profit), color: deal.gross_profit && deal.gross_profit > 0 ? '#4ade80' : RED }
                : null,
              netProfit != null
                ? { label: 'Net Profit', value: fmt(netProfit), color: netProfit > 0 ? GREEN : RED }
                : null,
              roi != null
                ? { label: 'ROI', value: fmtPct(roi, 1), color: roi >= 20 ? GREEN : roi >= 10 ? GOLD : TEXT_MUTED }
                : null,
              annualYield != null
                ? { label: 'Annual Yield', value: fmtPct(annualYield, 1), color: annualYield >= 10 ? GREEN : annualYield >= 7 ? GOLD : TEXT_MUTED }
                : null,
              deal.monthly_cashflow != null
                ? { label: 'Monthly Cashflow', value: `£${deal.monthly_cashflow}/mo`, color: deal.monthly_cashflow >= 500 ? GREEN : deal.monthly_cashflow >= 200 ? GOLD : TEXT_MUTED }
                : null,
            ].filter(Boolean).map((row: any, i, arr) => (
              <div key={row.label} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '7px 12px',
                borderBottom: i < arr.length - 1 ? `1px solid ${BORDER}` : undefined,
              }}>
                <span style={{ fontSize: 11.5, color: TEXT_MUTED }}>{row.label}</span>
                <span style={{ fontSize: 12, fontWeight: 600, color: row.color, fontVariantNumeric: 'tabular-nums' }}>{row.value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Score breakdown */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
            Score Breakdown
          </div>
          <div style={{ background: SURFACE2, border: `1px solid ${BORDER}`, borderRadius: 5, padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              { label: 'ROI (35%)', value: deal.score_roi, color: GREEN },
              { label: 'Discount (30%)', value: deal.score_discount, color: GOLD },
              { label: 'Risk (20%)', value: deal.score_risk, color: ACCENT_LIGHT },
              { label: 'Liquidity (15%)', value: deal.score_liquidity, color: '#a78bfa' },
            ].map(item => (
              <div key={item.label}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                  <span style={{ fontSize: 11, color: TEXT_MUTED }}>{item.label}</span>
                </div>
                <ScoreBar value={item.value} color={item.color} />
              </div>
            ))}
          </div>
        </div>

        {/* Risk + Conviction */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 16 }}>
          <div style={{ background: SURFACE2, border: `1px solid ${BORDER}`, borderRadius: 5, padding: '10px 12px' }}>
            <div style={{ fontSize: 10, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>Risk Level</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: riskCfg.color }}>{risk}</div>
          </div>
          <div style={{ background: SURFACE2, border: `1px solid ${BORDER}`, borderRadius: 5, padding: '10px 12px' }}>
            <div style={{ fontSize: 10, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>Confidence</div>
            <div style={{ fontSize: 13, fontWeight: 700, color: confCfg.color }}>{deal.confidence || 'Medium'}</div>
          </div>
        </div>

        {/* Exit Strategy */}
        {deal.exit_strategy && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>
              Exit Strategy
            </div>
            <div style={{ fontSize: 12.5, color: '#94a3b8', lineHeight: 1.5 }}>{deal.exit_strategy}</div>
          </div>
        )}

        {/* Opportunity Note */}
        {deal.opportunity_notes && (
          <div style={{ marginBottom: 14 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>
              Why This Deal
            </div>
            <div style={{
              background: 'rgba(16,185,129,0.05)', border: '1px solid rgba(16,185,129,0.12)',
              borderRadius: 4, padding: '8px 10px',
              fontSize: 12, color: '#6ee7b7', lineHeight: 1.6,
            }}>
              {deal.opportunity_notes}
            </div>
          </div>
        )}

        {/* Risk Note */}
        {deal.risk_notes && (
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>
              Key Risk
            </div>
            <div style={{
              background: 'rgba(245,158,11,0.05)', border: '1px solid rgba(245,158,11,0.15)',
              borderRadius: 4, padding: '8px 10px',
              fontSize: 12, color: '#fcd34d', lineHeight: 1.6,
            }}>
              {deal.risk_notes}
            </div>
          </div>
        )}

        {/* Full underwriting — locked */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
            Full Underwriting
          </div>
          <LockOverlay tier="analyst" />
        </div>

        {/* Comparable data — locked */}
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
            Comparable Sales Data
          </div>
          <LockOverlay tier="investor" />
        </div>

      </div>

      {/* Action footer */}
      <div style={{ borderTop: `1px solid ${BORDER}`, padding: '12px 18px', background: SURFACE2, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <button style={{
          width: '100%', padding: '9px 14px', background: ACCENT, border: 'none',
          borderRadius: 4, color: '#fff', fontSize: 13, fontWeight: 600, cursor: 'pointer',
        }}>
          View Full Underwriting
        </button>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          <button style={{
            padding: '7px 10px', background: 'transparent', border: `1px solid ${BORDER2}`,
            borderRadius: 4, color: TEXT_MUTED, fontSize: 12, fontWeight: 500, cursor: 'pointer',
          }}>
            Save Deal
          </button>
          <button style={{
            padding: '7px 10px', background: 'transparent', border: `1px solid ${BORDER2}`,
            borderRadius: 4, color: TEXT_MUTED, fontSize: 12, fontWeight: 500, cursor: 'pointer',
          }}>
            Export CSV
          </button>
        </div>
        <div style={{
          borderTop: `1px solid ${BORDER}`, paddingTop: 10, marginTop: 2,
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <div>
            <div style={{ fontSize: 10, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.06em' }}>Current Plan</div>
            <div style={{ fontSize: 11, fontWeight: 600, color: TEXT_MUTED, marginTop: 1 }}>Scout</div>
          </div>
          <button style={{
            padding: '5px 12px', background: `${GOLD}18`, border: `1px solid ${GOLD}40`,
            borderRadius: 4, color: GOLD_LIGHT, fontSize: 11, fontWeight: 700,
            cursor: 'pointer', letterSpacing: '0.02em',
          }}>
            Upgrade →
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main Dashboard ────────────────────────────────────────────────────────────

export default function DealsDashboard() {
  const router = useRouter()
  const [data, setData] = useState<DealsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selectedDeal, setSelectedDeal] = useState<Deal | null>(null)
  const [filters, setFilters] = useState({
    search: '', strategy: '', min_roi: '', min_discount: '', tier: '', sort: 'score',
  })

  const load = useCallback(async () => {
    const token = localStorage.getItem('nb_token')
    if (!token) { router.push('/login'); return }
    setLoading(true)
    const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const params = new URLSearchParams({ limit: '100', offset: '0', sort: filters.sort })
    if (filters.strategy) params.set('strategy', filters.strategy)
    if (filters.min_roi) params.set('min_roi', filters.min_roi)
    if (filters.min_discount) params.set('min_discount', filters.min_discount)
    if (filters.tier) params.set('tier', filters.tier)
    if (filters.search) params.set('search', filters.search)
    try {
      const res = await fetch(`${BASE}/deals?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) throw new Error('Failed to load')
      const d = await res.json()
      setData(d)
    } catch {
      // silently handle
    } finally {
      setLoading(false)
    }
  }, [filters, router])

  useEffect(() => { load() }, [load])

  const setFilter = (key: string, val: string) => {
    setFilters(f => ({ ...f, [key]: val }))
    setSelectedDeal(null)
  }

  const resetFilters = () => {
    setFilters({ search: '', strategy: '', min_roi: '', min_discount: '', tier: '', sort: 'score' })
    setSelectedDeal(null)
  }

  const kpis = data?.kpis
  const deals = data?.items || []

  const topStrategy = useMemo(() => {
    if (!kpis?.top_strategy) return '—'
    return strategyLabel(kpis.top_strategy)
  }, [kpis])

  // ── Input style helper ───────────────────────────────────────────────────
  const inputSx: React.CSSProperties = {
    background: SURFACE2, border: `1px solid ${BORDER}`, color: TEXT,
    padding: '7px 10px', borderRadius: 4, fontSize: 12.5, outline: 'none',
  }

  const labelSx: React.CSSProperties = {
    fontSize: 10, fontWeight: 600, letterSpacing: '0.07em', textTransform: 'uppercase',
    color: TEXT_DIM, marginBottom: 4,
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>

      {/* ── Page header ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', marginBottom: 18, flexWrap: 'wrap', gap: 8 }}>
        <div>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: TEXT, letterSpacing: '-0.02em', marginBottom: 3 }}>
            Deal Intelligence
          </h1>
          <p style={{ fontSize: 12, color: TEXT_MUTED }}>
            North East property pipeline · ranked by investment score
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={load} disabled={loading} style={{
            padding: '7px 14px', background: 'transparent', border: `1px solid ${BORDER}`,
            borderRadius: 4, color: TEXT_MUTED, fontSize: 12, cursor: 'pointer',
          }}>
            {loading ? 'Loading…' : 'Refresh'}
          </button>
          <button style={{
            padding: '7px 14px', background: 'transparent', border: `1px solid ${GOLD}40`,
            borderRadius: 4, color: GOLD_LIGHT, fontSize: 12, fontWeight: 600, cursor: 'pointer',
          }}>
            Export CSV
          </button>
        </div>
      </div>

      {/* ── KPI strip ───────────────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16 }}>
        <KpiCard
          label="Active Deals"
          value={loading ? '—' : (kpis?.active_deals ?? deals.length).toString()}
          sub="In current pipeline"
          accent="blue"
        />
        <KpiCard
          label="Avg Score"
          value={loading ? '—' : kpis?.avg_score != null ? kpis.avg_score.toFixed(1) : '—'}
          sub="Across all deals"
          accent="green"
        />
        <KpiCard
          label="Top Strategy"
          value={loading ? '—' : topStrategy}
          sub="By deal volume"
          accent="gold"
        />
        <KpiCard
          label="Coverage"
          value={loading ? '—' : kpis?.councils_covered ? `${kpis.councils_covered} councils` : '—'}
          sub="NE geography"
        />
      </div>

      {/* ── Filter bar ──────────────────────────────────────────────────── */}
      <div style={{
        background: SURFACE, border: `1px solid ${BORDER}`, borderRadius: 5,
        padding: '12px 14px', marginBottom: 12,
        display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end',
      }}>
        <div style={{ flex: '1 1 180px', minWidth: 0 }}>
          <div style={labelSx}>Search</div>
          <input
            value={filters.search}
            onChange={e => setFilter('search', e.target.value)}
            placeholder="Address / council / strategy…"
            style={{ ...inputSx, width: '100%', boxSizing: 'border-box' }}
          />
        </div>
        <div>
          <div style={labelSx}>Strategy</div>
          <select value={filters.strategy} onChange={e => setFilter('strategy', e.target.value)} style={inputSx}>
            <option value="">All strategies</option>
            {STRATEGIES.map(s => <option key={s} value={s}>{strategyLabel(s)}</option>)}
          </select>
        </div>
        <div>
          <div style={labelSx}>Min ROI %</div>
          <input
            type="number" value={filters.min_roi} onChange={e => setFilter('min_roi', e.target.value)}
            placeholder="e.g. 15" style={{ ...inputSx, width: 80 }}
          />
        </div>
        <div>
          <div style={labelSx}>Min Discount %</div>
          <input
            type="number" value={filters.min_discount} onChange={e => setFilter('min_discount', e.target.value)}
            placeholder="e.g. 15" style={{ ...inputSx, width: 90 }}
          />
        </div>
        <div>
          <div style={labelSx}>Tier</div>
          <select value={filters.tier} onChange={e => setFilter('tier', e.target.value)} style={inputSx}>
            <option value="">All tiers</option>
            <option value="S">S (80+)</option>
            <option value="A">A (70–79)</option>
            <option value="B">B (60–69)</option>
            <option value="C">C (below 60)</option>
          </select>
        </div>
        <div>
          <div style={labelSx}>Sort by</div>
          <select value={filters.sort} onChange={e => setFilter('sort', e.target.value)} style={inputSx}>
            <option value="score">Score</option>
            <option value="roi">ROI</option>
            <option value="discount">Discount</option>
            <option value="price">Price ↑</option>
            <option value="created">Newest</option>
          </select>
        </div>
        <button onClick={resetFilters} style={{
          padding: '7px 12px', background: 'transparent', border: `1px solid ${BORDER}`,
          borderRadius: 4, color: TEXT_DIM, fontSize: 12, cursor: 'pointer',
        }}>
          Reset
        </button>
      </div>

      {/* ── Main body: table + detail panel ─────────────────────────────── */}
      <div style={{ display: 'flex', gap: 0, flex: 1, minHeight: 0, border: `1px solid ${BORDER}`, borderRadius: 5, overflow: 'hidden' }}>

        {/* Deals table */}
        <div style={{ flex: 1, minWidth: 0, overflowX: 'auto', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12.5 }}>
            <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
              <tr style={{ background: SURFACE2, borderBottom: `1px solid ${BORDER}` }}>
                {[
                  { label: '#', w: 36 },
                  { label: 'Opportunity', w: 220 },
                  { label: 'Strategy', w: 100 },
                  { label: 'Price', w: 90 },
                  { label: 'Profit', w: 90 },
                  { label: 'ROI', w: 70 },
                  { label: 'Discount', w: 80 },
                  { label: 'Score', w: 90 },
                ].map(col => (
                  <th key={col.label} style={{
                    textAlign: 'left', padding: '9px 12px',
                    fontSize: 10, fontWeight: 600, letterSpacing: '0.07em',
                    textTransform: 'uppercase', color: TEXT_DIM, whiteSpace: 'nowrap',
                    width: col.w,
                  }}>
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} style={{ borderBottom: `1px solid ${BORDER}` }}>
                      {Array.from({ length: 8 }).map((_, j) => (
                        <td key={j} style={{ padding: '11px 12px' }}>
                          <div style={{ height: 11, background: BORDER2, borderRadius: 2, width: j === 1 ? 160 : 60, opacity: 0.6 }} />
                        </td>
                      ))}
                    </tr>
                  ))
                : deals.length === 0
                  ? (
                    <tr>
                      <td colSpan={8} style={{ padding: '48px 24px', textAlign: 'center', color: TEXT_MUTED }}>
                        <div style={{ marginBottom: 8, fontSize: 14 }}>No deals found</div>
                        <div style={{ fontSize: 12, color: TEXT_DIM }}>
                          Run <code style={{ background: SURFACE2, padding: '2px 6px', borderRadius: 3 }}>python scripts/seed_deals.py</code> to populate
                        </div>
                      </td>
                    </tr>
                  )
                  : deals.map((deal, i) => {
                      const isSelected = selectedDeal?.id === deal.id
                      const roi = deal.roi_pct ?? deal.roi
                      const annualYield = deal.annual_yield_pct ?? deal.annual_yield
                      const netProfit = deal.net_profit ?? deal.profit
                      const tier = deal.tier || 'C'
                      const tcfg = TIER_CONFIG[tier]

                      return (
                        <tr
                          key={deal.id}
                          onClick={() => setSelectedDeal(isSelected ? null : deal)}
                          style={{
                            borderBottom: `1px solid ${BORDER}`,
                            cursor: 'pointer',
                            background: isSelected ? `${ACCENT}10` : 'transparent',
                            borderLeft: isSelected ? `2px solid ${ACCENT}` : '2px solid transparent',
                            transition: 'background 0.1s',
                          }}
                          onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = SURFACE2 }}
                          onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = 'transparent' }}
                        >
                          {/* # */}
                          <td style={{ padding: '10px 12px', color: TEXT_DIM, fontWeight: 600 }}>
                            {deal.rank || i + 1}
                          </td>

                          {/* Opportunity */}
                          <td style={{ padding: '10px 12px', maxWidth: 220 }}>
                            <div style={{
                              color: TEXT, fontWeight: 500,
                              overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                              maxWidth: 210,
                            }}>
                              {deal.address}
                            </div>
                            <div style={{ fontSize: 11, color: TEXT_MUTED, marginTop: 2 }}>
                              {deal.postcode}{deal.council ? ` · ${deal.council}` : ''}
                            </div>
                          </td>

                          {/* Strategy */}
                          <td style={{ padding: '10px 12px' }}>
                            <StrategyTag strategy={deal.strategy} />
                          </td>

                          {/* Price */}
                          <td style={{ padding: '10px 12px', color: TEXT, fontVariantNumeric: 'tabular-nums', fontWeight: 500 }}>
                            {fmt(deal.purchase_price)}
                          </td>

                          {/* Profit */}
                          <td style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}>
                            {netProfit != null ? (
                              <span style={{ color: netProfit > 0 ? GREEN : RED, fontWeight: 600 }}>
                                {fmt(netProfit)}
                              </span>
                            ) : deal.monthly_cashflow != null ? (
                              <span style={{ color: GOLD, fontWeight: 600 }}>
                                £{deal.monthly_cashflow}/mo
                              </span>
                            ) : '—'}
                          </td>

                          {/* ROI */}
                          <td style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}>
                            {roi != null ? (
                              <span style={{
                                color: roi >= 20 ? GREEN : roi >= 12 ? GOLD : TEXT_MUTED,
                                fontWeight: 700,
                              }}>
                                {roi.toFixed(0)}%
                              </span>
                            ) : annualYield != null ? (
                              <span style={{ color: annualYield >= 10 ? GREEN : GOLD, fontWeight: 700 }}>
                                {annualYield.toFixed(1)}%y
                              </span>
                            ) : '—'}
                          </td>

                          {/* Discount */}
                          <td style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}>
                            {deal.discount_pct != null ? (
                              <span style={{
                                color: deal.discount_pct >= 20 ? GREEN : deal.discount_pct >= 10 ? GOLD : TEXT_MUTED,
                                fontWeight: 600,
                              }}>
                                {deal.discount_pct.toFixed(0)}%
                              </span>
                            ) : '—'}
                          </td>

                          {/* Score + tier */}
                          <td style={{ padding: '10px 12px' }}>
                            <TierBadge tier={tier} score={deal.overall_score} />
                          </td>
                        </tr>
                      )
                    })}
            </tbody>
          </table>
        </div>

        {/* Detail panel */}
        {selectedDeal && (
          <DetailPanel deal={selectedDeal} onClose={() => setSelectedDeal(null)} />
        )}
      </div>

      {/* ── Subscription framing ────────────────────────────────────────── */}
      <div style={{
        marginTop: 14, background: SURFACE2, border: `1px solid ${BORDER}`, borderRadius: 5,
        padding: '12px 18px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        flexWrap: 'wrap', gap: 10,
      }}>
        <div>
          <div style={{ fontSize: 12, fontWeight: 600, color: TEXT_MUTED, marginBottom: 3 }}>
            Northbridge Intelligence Plans
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            {[
              { name: 'Scout', desc: 'Basic pipeline, 10 deals/mo', active: true },
              { name: 'Analyst', desc: 'Full underwriting, unlimited deals', active: false },
              { name: 'Investor', desc: 'Comps, alerts, API access', active: false },
            ].map(plan => (
              <div key={plan.name} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <div style={{
                  width: 6, height: 6, borderRadius: '50%',
                  background: plan.active ? GREEN : BORDER2, flexShrink: 0,
                }} />
                <span style={{ fontSize: 11, color: plan.active ? TEXT_MUTED : TEXT_DIM, fontWeight: plan.active ? 600 : 400 }}>
                  {plan.name}
                </span>
                <span style={{ fontSize: 10, color: TEXT_DIM }}>{plan.desc}</span>
              </div>
            ))}
          </div>
        </div>
        <button style={{
          padding: '8px 18px', background: GOLD, border: 'none',
          borderRadius: 4, color: '#0a0c10', fontSize: 13, fontWeight: 700,
          cursor: 'pointer', letterSpacing: '0.01em',
        }}>
          Upgrade for Full Access
        </button>
      </div>

    </div>
  )
}
