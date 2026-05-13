'use client'

import { useState, useCallback } from 'react'
import type { SourcingDeal, DealOutreachState, OutreachStage } from '../types'

const SURFACE = '#0c1524'
const SURFACE2 = '#101e34'
const SURFACE3 = '#0a1120'
const BORDER = '#162038'
const BORDER2 = '#1e2e48'
const TEXT = '#dde6f4'
const TEXT_MUTED = '#546278'
const TEXT_DIM = '#2e3f55'
const ACCENT = '#1d4ed8'
const ACCENT_LIGHT = '#3b82f6'
const GOLD = '#c48f2a'
const GOLD_LIGHT = '#d4a94a'
const GREEN = '#10b981'
const RED = '#ef4444'
const AMBER = '#f59e0b'

const STAGE_ORDER: OutreachStage[] = ['new', 'contacted', 'buyer_sent', 'follow_up', 'fee_locked']
const STAGE_LABELS: Record<OutreachStage, string> = {
  new: 'New',
  contacted: 'Contacted',
  buyer_sent: 'Buyer Sent',
  follow_up: 'Follow Up',
  fee_locked: 'Fee Locked',
  passed: 'Passed',
}
const STAGE_COLORS: Record<OutreachStage, string> = {
  new: TEXT_DIM,
  contacted: ACCENT_LIGHT,
  buyer_sent: GOLD,
  follow_up: AMBER,
  fee_locked: GREEN,
  passed: TEXT_DIM,
}

const TIER_CONFIG: Record<string, { bg: string; border: string; color: string }> = {
  S: { bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.3)', color: '#10b981' },
  A: { bg: 'rgba(196,143,42,0.08)', border: 'rgba(196,143,42,0.3)', color: '#c48f2a' },
  B: { bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.3)', color: '#3b82f6' },
  C: { bg: 'rgba(90,110,138,0.07)', border: 'rgba(90,110,138,0.2)', color: '#5a6e8a' },
}

function fmt(n: number | null | undefined): string {
  if (n == null) return '—'
  return `£${n.toLocaleString('en-GB')}`
}

function fmtPct(n: number | null | undefined, dp = 1): string {
  if (n == null) return '—'
  return `${n.toFixed(dp)}%`
}

function relTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  return `${days}d ago`
}

interface Props {
  deal: SourcingDeal
  state: DealOutreachState
  onClose: () => void
  onSetStage: (s: OutreachStage) => void
  onToggleBuyerSent: () => void
  onToggleFollowUp: () => void
  onToggleFeeLocked: () => void
  onSetNotes: (notes: string) => void
}

export function RevenueDrawer({
  deal, state, onClose,
  onSetStage, onToggleBuyerSent, onToggleFollowUp, onToggleFeeLocked, onSetNotes,
}: Props) {
  const [tab, setTab] = useState<'intel' | 'outreach' | 'scripts'>('outreach')
  const [copiedScript, setCopiedScript] = useState(false)
  const [copiedTeaser, setCopiedTeaser] = useState(false)

  const tcfg = TIER_CONFIG[deal.tier] || TIER_CONFIG.C
  const roi = deal.roi_pct
  const annualYield = deal.annual_yield
  const netProfit = deal.net_profit

  const copyScript = useCallback(() => {
    navigator.clipboard.writeText(deal.agent_script).catch(() => {})
    setCopiedScript(true)
    setTimeout(() => setCopiedScript(false), 2000)
  }, [deal.agent_script])

  const copyTeaser = useCallback(() => {
    navigator.clipboard.writeText(deal.investor_teaser).catch(() => {})
    setCopiedTeaser(true)
    setTimeout(() => setCopiedTeaser(false), 2000)
  }, [deal.investor_teaser])

  const copyPhone = useCallback(() => {
    navigator.clipboard.writeText(deal.contact.agent_phone).catch(() => {})
  }, [deal.contact.agent_phone])

  const btnToggle = (active: boolean, activeColor: string): React.CSSProperties => ({
    flex: 1, padding: '8px 10px', borderRadius: 4, fontSize: 12, fontWeight: 700,
    cursor: 'pointer', border: active ? `1px solid ${activeColor}50` : `1px solid ${BORDER}`,
    background: active ? `${activeColor}15` : 'transparent',
    color: active ? activeColor : TEXT_DIM, textAlign: 'center' as const,
  })

  return (
    <div style={{
      width: 380, minWidth: 380, background: SURFACE, borderLeft: `1px solid ${BORDER}`,
      display: 'flex', flexDirection: 'column', height: '100%', overflow: 'hidden',
    }}>

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div style={{ background: SURFACE2, borderBottom: `1px solid ${BORDER}`, padding: '13px 16px', flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 5 }}>
              <span style={{
                background: tcfg.bg, border: `1px solid ${tcfg.border}`, color: tcfg.color,
                fontSize: 10.5, fontWeight: 800, padding: '2px 7px', borderRadius: 3,
              }}>
                {deal.tier} · {deal.overall_score.toFixed(0)}
              </span>
              <span style={{ fontSize: 10.5, color: STAGE_COLORS[state.stage], fontWeight: 600 }}>
                {STAGE_LABELS[state.stage]}
              </span>
              {state.fee_locked && (
                <span style={{ fontSize: 10.5, color: GREEN, fontWeight: 700 }}>🔒 Fee Locked</span>
              )}
            </div>
            <div style={{ fontSize: 13, fontWeight: 600, color: TEXT, lineHeight: 1.35 }}>
              {deal.address}
            </div>
            <div style={{ fontSize: 11, color: TEXT_MUTED, marginTop: 2 }}>
              {deal.postcode} · {deal.council} · {deal.source}
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'none', border: 'none', color: TEXT_DIM, cursor: 'pointer',
            fontSize: 18, padding: '2px 4px', flexShrink: 0, lineHeight: 1,
          }}>×</button>
        </div>

        {/* Contact bar */}
        <div style={{
          marginTop: 10, padding: '7px 10px',
          background: SURFACE3, border: `1px solid ${BORDER}`, borderRadius: 4,
          display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8,
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 11.5, fontWeight: 600, color: TEXT_MUTED }}>{deal.contact.agent_name}</div>
            <div style={{ fontSize: 10.5, color: TEXT_DIM }}>{deal.contact.agency}</div>
          </div>
          <button onClick={copyPhone} style={{
            padding: '4px 10px', background: `${ACCENT}18`, border: `1px solid ${ACCENT}35`,
            borderRadius: 3, color: ACCENT_LIGHT, fontSize: 11, fontWeight: 600, cursor: 'pointer',
            whiteSpace: 'nowrap',
          }}>
            📞 {deal.contact.agent_phone}
          </button>
        </div>
      </div>

      {/* ── Stage pipeline ───────────────────────────────────────────────── */}
      <div style={{ background: SURFACE3, borderBottom: `1px solid ${BORDER}`, padding: '8px 16px', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 1, alignItems: 'center' }}>
          {STAGE_ORDER.map((s, i) => {
            const isActive = state.stage === s
            const isPast = STAGE_ORDER.indexOf(state.stage) > i
            const color = isActive ? STAGE_COLORS[s] : isPast ? `${STAGE_COLORS[s]}70` : TEXT_DIM
            return (
              <button
                key={s}
                onClick={() => onSetStage(s)}
                style={{
                  flex: 1, padding: '5px 4px', background: isActive ? `${STAGE_COLORS[s]}10` : 'transparent',
                  border: isActive ? `1px solid ${STAGE_COLORS[s]}30` : `1px solid ${BORDER}`,
                  borderRadius: 3, color, fontSize: 10, fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer', textAlign: 'center' as const, whiteSpace: 'nowrap',
                }}
              >
                {STAGE_LABELS[s]}
              </button>
            )
          })}
          <button
            onClick={() => onSetStage('passed')}
            style={{
              padding: '5px 8px', background: 'transparent',
              border: state.stage === 'passed' ? `1px solid ${RED}30` : `1px solid ${BORDER}`,
              borderRadius: 3, color: state.stage === 'passed' ? RED : TEXT_DIM,
              fontSize: 10, fontWeight: 500, cursor: 'pointer',
            }}
          >
            Pass
          </button>
        </div>
      </div>

      {/* ── Revenue toggles ──────────────────────────────────────────────── */}
      <div style={{ background: SURFACE2, borderBottom: `1px solid ${BORDER}`, padding: '10px 16px', flexShrink: 0 }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button onClick={onToggleBuyerSent} style={btnToggle(state.buyer_sent, GOLD)}>
            {state.buyer_sent ? '✓ Buyer Sent' : 'Buyer Sent'}
          </button>
          <button onClick={onToggleFollowUp} style={btnToggle(state.follow_up, AMBER)}>
            {state.follow_up ? '✓ Follow Up' : 'Follow Up'}
          </button>
          <button onClick={onToggleFeeLocked} style={btnToggle(state.fee_locked, GREEN)}>
            {state.fee_locked ? '🔒 Fee Locked' : 'Fee Locked'}
          </button>
        </div>
      </div>

      {/* ── Tabs ─────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', background: SURFACE2, borderBottom: `1px solid ${BORDER}`, flexShrink: 0 }}>
        {[
          { key: 'outreach', label: 'Outreach' },
          { key: 'intel', label: 'Deal Intel' },
          { key: 'scripts', label: 'Scripts' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)} style={{
            flex: 1, padding: '8px 4px', background: 'transparent',
            border: 'none',
            borderBottom: tab === t.key ? `2px solid ${ACCENT}` : '2px solid transparent',
            color: tab === t.key ? TEXT : TEXT_DIM,
            fontSize: 11.5, fontWeight: tab === t.key ? 600 : 400, cursor: 'pointer',
          }}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab content ──────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 16px' }}>

        {tab === 'outreach' && (
          <div>
            {/* Notes */}
            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 10, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>
                Notes
              </div>
              <textarea
                value={state.notes}
                onChange={e => onSetNotes(e.target.value)}
                placeholder="Vendor situation, call notes, offer details…"
                rows={4}
                style={{
                  width: '100%', boxSizing: 'border-box', background: SURFACE3,
                  border: `1px solid ${BORDER}`, color: TEXT, borderRadius: 4,
                  padding: '8px 10px', fontSize: 12, resize: 'vertical', outline: 'none',
                  lineHeight: 1.5,
                }}
              />
            </div>

            {/* Activity log */}
            <div>
              <div style={{ fontSize: 10, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 8 }}>
                Activity Log
              </div>
              {state.activity.length === 0 ? (
                <div style={{ fontSize: 11.5, color: TEXT_DIM, padding: '10px 0' }}>
                  No activity yet — update stage or toggles above to log actions.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {state.activity.slice(0, 20).map(entry => (
                    <div key={entry.id} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                      padding: '5px 8px', background: SURFACE3, borderRadius: 3,
                      border: `1px solid ${BORDER}`,
                    }}>
                      <div>
                        <span style={{ fontSize: 11.5, color: TEXT_MUTED }}>{entry.action}</span>
                        {entry.note && <div style={{ fontSize: 10.5, color: TEXT_DIM, marginTop: 1 }}>{entry.note}</div>}
                      </div>
                      <span style={{ fontSize: 10, color: TEXT_DIM, whiteSpace: 'nowrap', marginLeft: 8 }}>
                        {relTime(entry.timestamp)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {tab === 'intel' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Tags */}
            {deal.tags.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                {deal.tags.map(tag => (
                  <span key={tag} style={{
                    fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 3,
                    background: `${ACCENT}15`, color: ACCENT_LIGHT, border: `1px solid ${ACCENT}25`,
                    letterSpacing: '0.03em', textTransform: 'uppercase' as const,
                  }}>{tag}</span>
                ))}
              </div>
            )}

            {/* Key numbers */}
            <div>
              <div style={{ fontSize: 10, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Key Numbers</div>
              <div style={{ background: SURFACE3, border: `1px solid ${BORDER}`, borderRadius: 4, overflow: 'hidden' }}>
                {[
                  { label: 'Asking Price', value: fmt(deal.asking_price), color: TEXT },
                  deal.estimated_value && { label: 'Est. Market Value', value: fmt(deal.estimated_value), color: TEXT },
                  deal.gdv && !deal.estimated_value && { label: 'GDV', value: fmt(deal.gdv), color: TEXT },
                  deal.discount_pct != null && {
                    label: 'Discount', value: fmtPct(deal.discount_pct),
                    color: deal.discount_pct >= 25 ? GREEN : deal.discount_pct >= 15 ? GOLD : TEXT_MUTED,
                  },
                  deal.refurb_cost && { label: 'Refurb Est.', value: fmt(deal.refurb_cost), color: TEXT_MUTED },
                  netProfit != null && {
                    label: 'Net Profit', value: fmt(netProfit),
                    color: netProfit > 0 ? GREEN : RED,
                  },
                  roi != null && {
                    label: 'ROI', value: fmtPct(roi),
                    color: roi >= 15 ? GREEN : roi >= 8 ? GOLD : TEXT_MUTED,
                  },
                  annualYield != null && {
                    label: 'Annual Yield', value: fmtPct(annualYield),
                    color: annualYield >= 12 ? GREEN : GOLD,
                  },
                  deal.monthly_cashflow != null && {
                    label: 'Monthly Cashflow', value: `£${deal.monthly_cashflow}/mo`,
                    color: deal.monthly_cashflow >= 500 ? GREEN : GOLD,
                  },
                ].filter(Boolean).map((row: any, i, arr) => (
                  <div key={row.label} style={{
                    display: 'flex', justifyContent: 'space-between',
                    padding: '6px 10px',
                    borderBottom: i < arr.length - 1 ? `1px solid ${BORDER}` : undefined,
                  }}>
                    <span style={{ fontSize: 11.5, color: TEXT_MUTED }}>{row.label}</span>
                    <span style={{ fontSize: 12, fontWeight: 600, color: row.color, fontVariantNumeric: 'tabular-nums' }}>{row.value}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Opportunity */}
            <div>
              <div style={{ fontSize: 10, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>Why This Deal</div>
              <div style={{
                background: 'rgba(16,185,129,0.04)', border: '1px solid rgba(16,185,129,0.12)',
                borderRadius: 4, padding: '8px 10px', fontSize: 12, color: '#6ee7b7', lineHeight: 1.6,
              }}>
                {deal.opportunity_notes}
              </div>
            </div>

            {/* Risk */}
            <div>
              <div style={{ fontSize: 10, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 5 }}>Key Risk</div>
              <div style={{
                background: 'rgba(245,158,11,0.04)', border: '1px solid rgba(245,158,11,0.12)',
                borderRadius: 4, padding: '8px 10px', fontSize: 12, color: '#fcd34d', lineHeight: 1.6,
              }}>
                {deal.risk_notes}
              </div>
            </div>

            {/* DOM & source */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
              <div style={{ background: SURFACE3, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '8px 10px' }}>
                <div style={{ fontSize: 10, color: TEXT_DIM, marginBottom: 3 }}>Days on Market</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: deal.days_on_market > 60 ? GOLD : TEXT_MUTED }}>
                  {deal.days_on_market}d
                </div>
              </div>
              <div style={{ background: SURFACE3, border: `1px solid ${BORDER}`, borderRadius: 4, padding: '8px 10px' }}>
                <div style={{ fontSize: 10, color: TEXT_DIM, marginBottom: 3 }}>Price Reductions</div>
                <div style={{ fontSize: 14, fontWeight: 700, color: deal.price_reductions > 0 ? AMBER : TEXT_MUTED }}>
                  {deal.price_reductions}
                </div>
              </div>
            </div>
          </div>
        )}

        {tab === 'scripts' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

            {/* Agent call script */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  Agent Call Script
                </div>
                <button onClick={copyScript} style={{
                  padding: '4px 10px', background: copiedScript ? `${GREEN}15` : `${ACCENT}15`,
                  border: `1px solid ${copiedScript ? GREEN : ACCENT}30`,
                  borderRadius: 3, color: copiedScript ? GREEN : ACCENT_LIGHT,
                  fontSize: 11, fontWeight: 600, cursor: 'pointer',
                }}>
                  {copiedScript ? '✓ Copied' : 'Copy Script'}
                </button>
              </div>
              <pre style={{
                background: SURFACE3, border: `1px solid ${BORDER}`,
                borderRadius: 4, padding: '10px 12px',
                fontSize: 11.5, color: TEXT_MUTED, lineHeight: 1.65,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, fontFamily: 'inherit',
              }}>
                {deal.agent_script}
              </pre>
            </div>

            {/* Investor teaser */}
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <div style={{ fontSize: 10, fontWeight: 600, color: TEXT_DIM, textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                  Investor Teaser
                </div>
                <button onClick={copyTeaser} style={{
                  padding: '4px 10px', background: copiedTeaser ? `${GREEN}15` : `${GOLD}15`,
                  border: `1px solid ${copiedTeaser ? GREEN : GOLD}30`,
                  borderRadius: 3, color: copiedTeaser ? GREEN : GOLD_LIGHT,
                  fontSize: 11, fontWeight: 600, cursor: 'pointer',
                }}>
                  {copiedTeaser ? '✓ Copied' : 'Copy Teaser'}
                </button>
              </div>
              <pre style={{
                background: SURFACE3, border: `1px solid ${BORDER}`,
                borderRadius: 4, padding: '10px 12px',
                fontSize: 11.5, color: TEXT_MUTED, lineHeight: 1.65,
                whiteSpace: 'pre-wrap', wordBreak: 'break-word', margin: 0, fontFamily: 'inherit',
              }}>
                {deal.investor_teaser}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
