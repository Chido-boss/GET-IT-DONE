'use client'

import { useState } from 'react'
import type { SourcingDeal, DealOutreachState, OutreachStage } from '../types'

const SURFACE2 = '#101e34'
const BORDER = '#162038'
const TEXT = '#dde6f4'
const TEXT_MUTED = '#546278'
const TEXT_DIM = '#2e3f55'
const ACCENT = '#1d4ed8'
const ACCENT_LIGHT = '#3b82f6'
const GOLD = '#c48f2a'
const GREEN = '#10b981'
const RED = '#ef4444'
const AMBER = '#f59e0b'

const TIER_CONFIG: Record<string, { bg: string; border: string; color: string }> = {
  S: { bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.3)', color: '#10b981' },
  A: { bg: 'rgba(196,143,42,0.08)', border: 'rgba(196,143,42,0.3)', color: '#c48f2a' },
  B: { bg: 'rgba(59,130,246,0.08)', border: 'rgba(59,130,246,0.3)', color: '#3b82f6' },
  C: { bg: 'rgba(90,110,138,0.07)', border: 'rgba(90,110,138,0.2)', color: '#5a6e8a' },
}

const STRATEGY_COLORS: Record<string, string> = {
  flip: '#8b5cf6', light_refurb: '#7c3aed', brrr: '#2563eb', btl: '#0891b2',
  income_hold: '#0e7490', hmo: '#0f766e', conversion: '#b45309', auction: '#dc2626',
}

const STRATEGY_LABELS: Record<string, string> = {
  flip: 'Flip', light_refurb: 'Light Refurb', brrr: 'BRRR', btl: 'BTL',
  income_hold: 'Income Hold', hmo: 'HMO', conversion: 'Conv.', auction: 'Auction',
}

const STAGE_CONFIG: Record<OutreachStage, { color: string; label: string }> = {
  new: { color: TEXT_DIM, label: 'New' },
  contacted: { color: ACCENT_LIGHT, label: 'Contacted' },
  buyer_sent: { color: GOLD, label: 'Buyer Sent' },
  follow_up: { color: AMBER, label: 'Follow Up' },
  fee_locked: { color: GREEN, label: 'Fee Locked' },
  passed: { color: TEXT_DIM, label: 'Passed' },
}

function fmt(n: number | null | undefined): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `£${(n / 1_000_000).toFixed(1)}m`
  if (n >= 1_000) return `£${(n / 1_000).toFixed(0)}k`
  return `£${n}`
}

interface Props {
  deal: SourcingDeal
  state: DealOutreachState
  rank: number
  isSelected: boolean
  onSelect: () => void
  onStage: (stage: OutreachStage) => void
  onToggleBuyerSent: () => void
  onToggleFollowUp: () => void
  onToggleFeeLocked: () => void
}

export function DealRow({
  deal, state, rank, isSelected, onSelect,
  onStage, onToggleBuyerSent, onToggleFollowUp, onToggleFeeLocked,
}: Props) {
  const [copied, setCopied] = useState<'script' | 'teaser' | null>(null)
  const tier = deal.tier
  const tcfg = TIER_CONFIG[tier] || TIER_CONFIG.C
  const scfg = STRATEGY_COLORS[deal.strategy] || ACCENT_LIGHT
  const stageCfg = STAGE_CONFIG[state.stage]

  const roi = deal.roi_pct
  const yield_ = deal.annual_yield
  const netProfit = deal.net_profit

  const copy = (type: 'script' | 'teaser') => {
    const text = type === 'script' ? deal.agent_script : deal.investor_teaser
    navigator.clipboard.writeText(text).catch(() => {})
    setCopied(type)
    setTimeout(() => setCopied(null), 1800)
  }

  const btnBase: React.CSSProperties = {
    padding: '3px 8px', borderRadius: 3, fontSize: 10.5, fontWeight: 600,
    cursor: 'pointer', border: `1px solid ${BORDER}`, whiteSpace: 'nowrap',
  }

  return (
    <tr
      style={{
        borderBottom: `1px solid ${BORDER}`,
        background: isSelected ? `${ACCENT}0d` : 'transparent',
        borderLeft: isSelected ? `2px solid ${ACCENT}` : '2px solid transparent',
        cursor: 'pointer',
      }}
      onMouseEnter={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = SURFACE2 }}
      onMouseLeave={e => { if (!isSelected) (e.currentTarget as HTMLElement).style.background = 'transparent' }}
    >
      {/* Rank */}
      <td style={{ padding: '8px 10px', color: TEXT_DIM, fontWeight: 600, fontSize: 11 }}>
        {rank}
      </td>

      {/* Score/Tier */}
      <td style={{ padding: '8px 10px' }} onClick={onSelect}>
        <span style={{
          display: 'inline-flex', alignItems: 'center', gap: 3,
          background: tcfg.bg, border: `1px solid ${tcfg.border}`, color: tcfg.color,
          fontSize: 10.5, fontWeight: 800, padding: '2px 7px', borderRadius: 3,
          whiteSpace: 'nowrap',
        }}>
          {tier} · {deal.overall_score.toFixed(0)}
        </span>
      </td>

      {/* Address */}
      <td style={{ padding: '8px 10px', maxWidth: 200 }} onClick={onSelect}>
        <div style={{ color: TEXT, fontWeight: 500, fontSize: 12.5, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 195 }}>
          {deal.address}
        </div>
        <div style={{ fontSize: 10.5, color: TEXT_MUTED, marginTop: 1 }}>
          {deal.postcode} · {deal.council}
          {deal.bedrooms ? ` · ${deal.bedrooms}bed` : ''}
        </div>
      </td>

      {/* Strategy */}
      <td style={{ padding: '8px 10px' }}>
        <span style={{
          fontSize: 10.5, fontWeight: 600, padding: '2px 6px', borderRadius: 3,
          background: `${scfg}15`, color: scfg, border: `1px solid ${scfg}28`,
          textTransform: 'uppercase' as const, whiteSpace: 'nowrap',
        }}>
          {STRATEGY_LABELS[deal.strategy] || deal.strategy}
        </span>
      </td>

      {/* Source */}
      <td style={{ padding: '8px 10px', fontSize: 11, color: TEXT_MUTED, whiteSpace: 'nowrap' }}>
        {deal.source}
      </td>

      {/* Price */}
      <td style={{ padding: '8px 10px', fontVariantNumeric: 'tabular-nums', fontSize: 12, fontWeight: 600, color: TEXT, whiteSpace: 'nowrap' }}>
        {fmt(deal.asking_price)}
      </td>

      {/* Profit/Yield */}
      <td style={{ padding: '8px 10px', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {netProfit != null ? (
          <span style={{ fontSize: 12, fontWeight: 600, color: netProfit > 0 ? GREEN : RED }}>
            {fmt(netProfit)}
          </span>
        ) : deal.monthly_cashflow != null ? (
          <span style={{ fontSize: 11, fontWeight: 600, color: GOLD }}>
            £{deal.monthly_cashflow}/mo
          </span>
        ) : '—'}
      </td>

      {/* ROI/Yield% */}
      <td style={{ padding: '8px 10px', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {roi != null ? (
          <span style={{ fontSize: 12, fontWeight: 700, color: roi >= 15 ? GREEN : roi >= 8 ? GOLD : TEXT_MUTED }}>
            {roi.toFixed(0)}%
          </span>
        ) : yield_ != null ? (
          <span style={{ fontSize: 12, fontWeight: 700, color: yield_ >= 12 ? GREEN : GOLD }}>
            {yield_.toFixed(1)}%y
          </span>
        ) : '—'}
      </td>

      {/* Discount */}
      <td style={{ padding: '8px 10px', fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap' }}>
        {deal.discount_pct != null ? (
          <span style={{ fontSize: 12, fontWeight: 600, color: deal.discount_pct >= 25 ? GREEN : deal.discount_pct >= 15 ? GOLD : TEXT_MUTED }}>
            {deal.discount_pct.toFixed(0)}%
          </span>
        ) : '—'}
      </td>

      {/* DOM */}
      <td style={{ padding: '8px 10px', fontSize: 11, color: deal.days_on_market > 60 ? GOLD : TEXT_MUTED, whiteSpace: 'nowrap' }}>
        {deal.days_on_market}d
        {deal.price_reductions > 0 && (
          <span style={{ marginLeft: 4, fontSize: 10, color: AMBER }}>↓{deal.price_reductions}</span>
        )}
      </td>

      {/* Stage indicator */}
      <td style={{ padding: '8px 10px' }}>
        <span style={{ fontSize: 10.5, fontWeight: 600, color: stageCfg.color, whiteSpace: 'nowrap' }}>
          {stageCfg.label}
        </span>
      </td>

      {/* Action buttons */}
      <td style={{ padding: '8px 8px' }}>
        <div style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
          <button
            onClick={onSelect}
            style={{ ...btnBase, background: isSelected ? `${ACCENT}20` : 'transparent', color: isSelected ? ACCENT_LIGHT : TEXT_MUTED }}
          >
            {isSelected ? 'Close' : 'View →'}
          </button>
          <button
            onClick={e => { e.stopPropagation(); copy('script') }}
            style={{ ...btnBase, background: 'transparent', color: copied === 'script' ? GREEN : TEXT_DIM }}
          >
            {copied === 'script' ? '✓' : 'Script'}
          </button>
          <button
            onClick={e => { e.stopPropagation(); copy('teaser') }}
            style={{ ...btnBase, background: 'transparent', color: copied === 'teaser' ? GREEN : TEXT_DIM }}
          >
            {copied === 'teaser' ? '✓' : 'Teaser'}
          </button>
          <button
            onClick={e => { e.stopPropagation(); onToggleBuyerSent() }}
            style={{
              ...btnBase,
              background: state.buyer_sent ? 'rgba(196,143,42,0.12)' : 'transparent',
              color: state.buyer_sent ? GOLD : TEXT_DIM,
              border: state.buyer_sent ? `1px solid ${GOLD}40` : `1px solid ${BORDER}`,
            }}
          >
            {state.buyer_sent ? '✓ Buyer' : 'Buyer'}
          </button>
          <button
            onClick={e => { e.stopPropagation(); onToggleFeeLocked() }}
            style={{
              ...btnBase,
              background: state.fee_locked ? 'rgba(16,185,129,0.1)' : 'transparent',
              color: state.fee_locked ? GREEN : TEXT_DIM,
              border: state.fee_locked ? `1px solid ${GREEN}40` : `1px solid ${BORDER}`,
            }}
          >
            {state.fee_locked ? '🔒 Fee' : 'Fee'}
          </button>
        </div>
      </td>
    </tr>
  )
}
