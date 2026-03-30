'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { format } from 'date-fns'
import { ArrowUpRight, RefreshCw } from 'lucide-react'
import { api } from '@/lib/api'
import { StatCard } from '@/components/ui/StatCard'
import { ScoreBadge } from '@/components/ui/ScoreBadge'
import { formatPrice, formatDiscount, propertyTypeLabel } from '@/lib/utils'
import type { DashboardStats, Listing } from '@/types'

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [topDeals, setTopDeals] = useState<Listing[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function fetchData() {
    setLoading(true)
    setError(null)
    try {
      const [statsData, dealsData] = await Promise.all([
        api.dashboard.stats(),
        api.listings.list({ min_score: '0', limit: '10', sort: 'score' }),
      ])
      setStats(statsData)
      setTopDeals(dealsData.items)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const today = format(new Date(), 'EEEE d MMMM yyyy')

  return (
    <div>
      {/* Page header */}
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-start',
          justifyContent: 'space-between',
          marginBottom: '28px',
          flexWrap: 'wrap',
          gap: '12px',
        }}
      >
        <div>
          <h1
            style={{
              fontSize: '1.4rem',
              fontWeight: 700,
              color: '#f1f5f9',
              letterSpacing: '-0.02em',
              marginBottom: '4px',
            }}
          >
            Intelligence Dashboard
          </h1>
          <p style={{ fontSize: '0.82rem', color: '#64748b' }}>{today}</p>
        </div>
        <button
          onClick={fetchData}
          disabled={loading}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            backgroundColor: 'transparent',
            border: '1px solid #1e2d45',
            borderRadius: '4px',
            padding: '7px 14px',
            fontSize: '0.82rem',
            color: '#64748b',
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          <RefreshCw size={13} style={{ animation: loading ? 'spin 0.7s linear infinite' : undefined }} />
          Refresh
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </button>
      </div>

      {error && (
        <div
          style={{
            backgroundColor: 'rgba(185,28,28,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: '4px',
            padding: '12px 16px',
            color: '#fca5a5',
            fontSize: '0.85rem',
            marginBottom: '20px',
          }}
        >
          {error}
        </div>
      )}

      {/* KPI Row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(4, 1fr)',
          gap: '12px',
          marginBottom: '28px',
        }}
      >
        <StatCard
          title="Active Listings"
          value={loading ? '—' : (stats?.total_listings ?? 0).toLocaleString()}
          subtitle="Tracked across all councils"
          accent="default"
        />
        <StatCard
          title="High-Score Deals"
          value={loading ? '—' : (stats?.high_score_count ?? 0).toLocaleString()}
          subtitle="Score ≥ 70 — act now"
          accent="green"
        />
        <StatCard
          title="Planning Applications"
          value={loading ? '—' : (stats?.planning_count ?? 0).toLocaleString()}
          subtitle="Across all NE councils"
          accent="blue"
        />
        <StatCard
          title="Alerts This Week"
          value={loading ? '—' : (stats?.alerts_this_week ?? 0).toLocaleString()}
          subtitle="New deal & planning alerts"
          accent="amber"
        />
      </div>

      {/* Two-column layout */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 280px',
          gap: '16px',
          alignItems: 'start',
        }}
      >
        {/* Top Deals Table */}
        <div
          style={{
            backgroundColor: '#0f1729',
            border: '1px solid #1e2d45',
            borderRadius: '4px',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '14px 18px',
              borderBottom: '1px solid #1e2d45',
            }}
          >
            <h2
              style={{
                fontSize: '0.9rem',
                fontWeight: 600,
                color: '#e2e8f0',
              }}
            >
              Top Deals Today
            </h2>
            <Link
              href="/listings"
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontSize: '0.78rem',
                color: '#2563eb',
                textDecoration: 'none',
              }}
            >
              View all <ArrowUpRight size={12} />
            </Link>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  {[
                    'Address',
                    'Council',
                    'Price',
                    'Est. Value',
                    'Discount',
                    'BMV',
                    'Distress',
                    'Score',
                    '',
                  ].map((h) => (
                    <th
                      key={h}
                      style={{
                        padding: '8px 14px',
                        fontSize: '0.67rem',
                        fontWeight: 600,
                        letterSpacing: '0.08em',
                        textTransform: 'uppercase',
                        color: '#475569',
                        borderBottom: '1px solid #1e2d45',
                        textAlign: 'left',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {loading
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <tr key={i}>
                        {Array.from({ length: 9 }).map((_, j) => (
                          <td key={j} style={{ padding: '9px 14px' }}>
                            <div
                              style={{
                                height: '12px',
                                backgroundColor: '#1e2d45',
                                borderRadius: '2px',
                                opacity: 0.5,
                                width: j === 0 ? '140px' : '60px',
                              }}
                            />
                          </td>
                        ))}
                      </tr>
                    ))
                  : topDeals.map((deal) => {
                      const discountPct = deal.score?.discount_pct
                      const estValue = deal.score?.estimated_fair_value
                      return (
                        <tr
                          key={deal.id}
                          style={{ cursor: 'pointer' }}
                        >
                          <td style={{ padding: '8px 14px' }}>
                            <div
                              style={{
                                fontSize: '0.82rem',
                                color: '#e2e8f0',
                                fontWeight: 500,
                                maxWidth: '200px',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              {deal.address}
                            </div>
                            <div style={{ fontSize: '0.72rem', color: '#475569' }}>
                              {deal.postcode} · {propertyTypeLabel(deal.property_type)}
                            </div>
                          </td>
                          <td
                            style={{
                              padding: '8px 14px',
                              fontSize: '0.78rem',
                              color: '#64748b',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {deal.council ?? '—'}
                          </td>
                          <td
                            style={{
                              padding: '8px 14px',
                              fontSize: '0.82rem',
                              color: '#e2e8f0',
                              fontFamily: 'monospace',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {formatPrice(deal.asking_price)}
                          </td>
                          <td
                            style={{
                              padding: '8px 14px',
                              fontSize: '0.82rem',
                              color: '#64748b',
                              fontFamily: 'monospace',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {estValue ? formatPrice(estValue) : '—'}
                          </td>
                          <td style={{ padding: '8px 14px', whiteSpace: 'nowrap' }}>
                            {discountPct != null ? (
                              <span
                                style={{
                                  fontSize: '0.8rem',
                                  fontWeight: 600,
                                  color: discountPct < 0 ? '#10b981' : '#ef4444',
                                  fontFamily: 'monospace',
                                }}
                              >
                                {discountPct < 0 ? '▼' : '▲'}{' '}
                                {formatDiscount(discountPct)}
                              </span>
                            ) : (
                              <span style={{ color: '#475569' }}>—</span>
                            )}
                          </td>
                          <td style={{ padding: '8px 14px' }}>
                            {deal.score ? (
                              <span
                                style={{
                                  fontSize: '0.78rem',
                                  fontFamily: 'monospace',
                                  color: '#94a3b8',
                                }}
                              >
                                {deal.score.bmv_score.toFixed(0)}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td style={{ padding: '8px 14px' }}>
                            {deal.score ? (
                              <span
                                style={{
                                  fontSize: '0.78rem',
                                  fontFamily: 'monospace',
                                  color: '#94a3b8',
                                }}
                              >
                                {deal.score.distress_score.toFixed(0)}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td style={{ padding: '8px 14px' }}>
                            {deal.score ? (
                              <ScoreBadge score={deal.score.overall_score} />
                            ) : (
                              <span style={{ color: '#475569', fontSize: '0.8rem' }}>
                                Unscored
                              </span>
                            )}
                          </td>
                          <td style={{ padding: '8px 14px' }}>
                            <Link
                              href={`/listings/${deal.id}`}
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '4px',
                                fontSize: '0.75rem',
                                color: '#2563eb',
                                textDecoration: 'none',
                                whiteSpace: 'nowrap',
                              }}
                            >
                              View <ArrowUpRight size={11} />
                            </Link>
                          </td>
                        </tr>
                      )
                    })}
              </tbody>
            </table>

            {!loading && topDeals.length === 0 && (
              <div
                style={{
                  padding: '32px',
                  textAlign: 'center',
                  color: '#475569',
                  fontSize: '0.85rem',
                }}
              >
                No deals available. Import data to get started.
              </div>
            )}
          </div>
        </div>

        {/* Councils Breakdown */}
        <div
          style={{
            backgroundColor: '#0f1729',
            border: '1px solid #1e2d45',
            borderRadius: '4px',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              padding: '14px 18px',
              borderBottom: '1px solid #1e2d45',
            }}
          >
            <h2 style={{ fontSize: '0.9rem', fontWeight: 600, color: '#e2e8f0' }}>
              Listings by Council
            </h2>
          </div>
          <div>
            {loading
              ? Array.from({ length: 6 }).map((_, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      padding: '9px 18px',
                      borderBottom: '1px solid #1e2d45',
                    }}
                  >
                    <div
                      style={{
                        height: '12px',
                        backgroundColor: '#1e2d45',
                        borderRadius: '2px',
                        width: '120px',
                      }}
                    />
                    <div
                      style={{
                        height: '12px',
                        backgroundColor: '#1e2d45',
                        borderRadius: '2px',
                        width: '30px',
                      }}
                    />
                  </div>
                ))
              : stats?.top_councils.map((c, i) => {
                  const maxCount = stats.top_councils[0]?.count ?? 1
                  const pct = (c.count / maxCount) * 100
                  return (
                    <div
                      key={c.council}
                      style={{
                        padding: '9px 18px',
                        borderBottom:
                          i < (stats.top_councils.length - 1)
                            ? '1px solid #1e2d45'
                            : undefined,
                      }}
                    >
                      <div
                        style={{
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          marginBottom: '5px',
                        }}
                      >
                        <span
                          style={{
                            fontSize: '0.8rem',
                            color: '#94a3b8',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            maxWidth: '160px',
                          }}
                        >
                          {c.council}
                        </span>
                        <span
                          style={{
                            fontSize: '0.8rem',
                            fontWeight: 600,
                            color: '#d97706',
                            fontFamily: 'monospace',
                          }}
                        >
                          {c.count}
                        </span>
                      </div>
                      <div
                        style={{
                          height: '3px',
                          backgroundColor: '#1e2d45',
                          borderRadius: '2px',
                        }}
                      >
                        <div
                          style={{
                            height: '100%',
                            width: `${pct}%`,
                            backgroundColor: '#1d4ed8',
                            borderRadius: '2px',
                            transition: 'width 0.4s ease',
                          }}
                        />
                      </div>
                    </div>
                  )
                })}

            {!loading && (!stats?.top_councils || stats.top_councils.length === 0) && (
              <div
                style={{
                  padding: '24px 18px',
                  color: '#475569',
                  fontSize: '0.82rem',
                  textAlign: 'center',
                }}
              >
                No data available
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
