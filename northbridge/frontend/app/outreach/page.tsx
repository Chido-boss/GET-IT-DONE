'use client'

import { useState, useCallback } from 'react'
import { usePipeline, SEED_DEALS } from './hooks/usePipeline'
import { PipelineToolbar } from './components/PipelineToolbar'
import { DealRow } from './components/DealRow'
import { RevenueDrawer } from './components/RevenueDrawer'
import type { SourcingDeal, OutreachStage } from './types'

const BG = '#070d1a'
const SURFACE = '#0c1524'
const SURFACE2 = '#101e34'
const BORDER = '#162038'
const TEXT = '#dde6f4'
const TEXT_MUTED = '#546278'
const TEXT_DIM = '#2e3f55'
const ACCENT = '#1d4ed8'
const GOLD = '#c48f2a'
const GOLD_LIGHT = '#d4a94a'
const GREEN = '#10b981'

// ── CSV export ────────────────────────────────────────────────────────────────

function exportCSV(deals: SourcingDeal[], pipelineState: Record<string, any>) {
  const headers = [
    'Address', 'Council', 'Postcode', 'Strategy', 'Source', 'Tier', 'Score',
    'Asking Price', 'Est. Value', 'Discount%', 'Refurb', 'Net Profit', 'ROI%',
    'Annual Yield%', 'DOM', 'Price Cuts', 'Stage', 'Buyer Sent', 'Follow Up', 'Fee Locked', 'Notes',
  ]
  const rows = deals.map(d => {
    const state = pipelineState[d.id] || {}
    return [
      d.address, d.council, d.postcode, d.strategy, d.source, d.tier, d.overall_score.toFixed(0),
      d.asking_price, d.estimated_value ?? '', d.discount_pct?.toFixed(1) ?? '',
      d.refurb_cost ?? '', d.net_profit ?? '', d.roi_pct?.toFixed(1) ?? '',
      d.annual_yield?.toFixed(1) ?? '', d.days_on_market, d.price_reductions,
      state.stage || 'new', state.buyer_sent ? 'Yes' : 'No',
      state.follow_up ? 'Yes' : 'No', state.fee_locked ? 'Yes' : 'No',
      (state.notes || '').replace(/\n/g, ' '),
    ]
  })
  const csv = [headers, ...rows].map(r => r.map(v => `"${v}"`).join(',')).join('\n')
  const blob = new Blob([csv], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `northbridge-pipeline-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function OutreachPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const {
    filteredDeals, filters, setFilters, stats, pipelineCount,
    getDealState, setStage, toggleBuyerSent, toggleFollowUp, toggleFeeLocked, setNotes,
  } = usePipeline()

  const selectedDeal = selectedId ? SEED_DEALS.find(d => d.id === selectedId) ?? null : null
  const selectedState = selectedId ? getDealState(selectedId) : null

  const handleSelect = useCallback((id: string) => {
    setSelectedId(prev => prev === id ? null : id)
  }, [])

  const handleExportCSV = useCallback(() => {
    const pipelineMap: Record<string, any> = {}
    for (const deal of SEED_DEALS) {
      pipelineMap[deal.id] = getDealState(deal.id)
    }
    exportCSV(filteredDeals, pipelineMap)
  }, [filteredDeals, getDealState])

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', minHeight: '100vh',
      background: BG, color: TEXT, fontFamily: 'system-ui, -apple-system, sans-serif',
    }}>

      {/* ── Top bar ────────────────────────────────────────────────────── */}
      <div style={{
        background: SURFACE, borderBottom: `1px solid ${BORDER}`,
        padding: '10px 18px', display: 'flex', alignItems: 'center',
        justifyContent: 'space-between', flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {/* Logo mark */}
          <div style={{
            width: 26, height: 26, background: '#1d4ed8', borderRadius: 3,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 13, fontWeight: 800, color: '#fff', flexShrink: 0,
          }}>N</div>
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: TEXT, letterSpacing: '-0.01em' }}>
              Northbridge Intelligence
            </div>
            <div style={{ fontSize: 10.5, fontWeight: 600, color: GOLD, letterSpacing: '0.05em', textTransform: 'uppercase' }}>
              Outreach Desk · V13
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {stats.potentialRevenue > 0 && (
            <div style={{
              padding: '4px 12px', background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: 4, fontSize: 11, fontWeight: 700, color: GREEN,
            }}>
              {stats.feeLockedDeals.length} Fee Locked · Est. £{stats.potentialRevenue.toLocaleString()}
            </div>
          )}
          <a
            href="/dashboard"
            style={{
              padding: '5px 12px', background: 'transparent', border: `1px solid ${BORDER}`,
              borderRadius: 4, color: TEXT_MUTED, fontSize: 11, fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            ← Intelligence
          </a>
          <a
            href="/deals"
            style={{
              padding: '5px 12px', background: 'transparent', border: `1px solid ${BORDER}`,
              borderRadius: 4, color: TEXT_MUTED, fontSize: 11, fontWeight: 500,
              textDecoration: 'none',
            }}
          >
            Deal Pipeline
          </a>
        </div>
      </div>

      {/* ── Main body ──────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '14px 18px', gap: 12, minHeight: 0 }}>

        {/* Toolbar */}
        <PipelineToolbar
          filters={filters}
          setFilters={setFilters}
          stats={stats}
          totalDeals={pipelineCount}
          filteredCount={filteredDeals.length}
          onExportCSV={handleExportCSV}
        />

        {/* Table + Drawer */}
        <div style={{
          flex: 1, display: 'flex', border: `1px solid ${BORDER}`,
          borderRadius: 5, overflow: 'hidden', minHeight: 400,
        }}>

          {/* Deal table */}
          <div style={{ flex: 1, overflowX: 'auto', overflowY: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                <tr style={{ background: SURFACE2, borderBottom: `1px solid ${BORDER}` }}>
                  {[
                    { label: '#', w: 32 },
                    { label: 'Score', w: 68 },
                    { label: 'Opportunity', w: 200 },
                    { label: 'Strategy', w: 90 },
                    { label: 'Source', w: 80 },
                    { label: 'Price', w: 70 },
                    { label: 'Profit', w: 80 },
                    { label: 'ROI/Yld', w: 65 },
                    { label: 'Disc%', w: 55 },
                    { label: 'DOM', w: 55 },
                    { label: 'Stage', w: 80 },
                    { label: 'Actions', w: 260 },
                  ].map(col => (
                    <th key={col.label} style={{
                      textAlign: 'left', padding: '7px 10px',
                      fontSize: 9.5, fontWeight: 600, letterSpacing: '0.08em',
                      textTransform: 'uppercase', color: TEXT_DIM,
                      whiteSpace: 'nowrap', width: col.w,
                    }}>
                      {col.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filteredDeals.length === 0 ? (
                  <tr>
                    <td colSpan={12} style={{ padding: '40px 20px', textAlign: 'center', color: TEXT_DIM, fontSize: 13 }}>
                      No deals match current filters.
                    </td>
                  </tr>
                ) : filteredDeals.map((deal, i) => (
                  <DealRow
                    key={deal.id}
                    deal={deal}
                    state={getDealState(deal.id)}
                    rank={i + 1}
                    isSelected={selectedId === deal.id}
                    onSelect={() => handleSelect(deal.id)}
                    onStage={(s: OutreachStage) => setStage(deal.id, s)}
                    onToggleBuyerSent={() => toggleBuyerSent(deal.id)}
                    onToggleFollowUp={() => toggleFollowUp(deal.id)}
                    onToggleFeeLocked={() => toggleFeeLocked(deal.id)}
                  />
                ))}
              </tbody>
            </table>
          </div>

          {/* Revenue Drawer */}
          {selectedDeal && selectedState && (
            <RevenueDrawer
              deal={selectedDeal}
              state={selectedState}
              onClose={() => setSelectedId(null)}
              onSetStage={(s) => setStage(selectedDeal.id, s)}
              onToggleBuyerSent={() => toggleBuyerSent(selectedDeal.id)}
              onToggleFollowUp={() => toggleFollowUp(selectedDeal.id)}
              onToggleFeeLocked={() => toggleFeeLocked(selectedDeal.id)}
              onSetNotes={(n) => setNotes(selectedDeal.id, n)}
            />
          )}
        </div>
      </div>
    </div>
  )
}
