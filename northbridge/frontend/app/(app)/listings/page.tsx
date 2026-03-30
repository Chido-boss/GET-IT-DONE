'use client'

import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { ArrowUpRight, ChevronLeft, ChevronRight } from 'lucide-react'
import { api } from '@/lib/api'
import { ScoreBadge } from '@/components/ui/ScoreBadge'
import { SignalChip } from '@/components/ui/SignalChip'
import { FilterBar } from '@/components/ui/FilterBar'
import { formatPrice, propertyTypeLabel } from '@/lib/utils'
import type { Listing } from '@/types'

const COUNCILS = [
  'Gateshead Council',
  'Newcastle City Council',
  'Sunderland City Council',
  'Durham County Council',
  'Middlesbrough Council',
  'Stockton-on-Tees Borough Council',
  'Hartlepool Borough Council',
  'Redcar and Cleveland Borough Council',
  'Northumberland County Council',
  'South Tyneside Council',
]

const PROPERTY_TYPES = [
  { value: 'D', label: 'Detached' },
  { value: 'S', label: 'Semi-Detached' },
  { value: 'T', label: 'Terraced' },
  { value: 'F', label: 'Flat' },
  { value: 'O', label: 'Other' },
  { value: 'C', label: 'Commercial' },
]

const PAGE_SIZE = 50

function getSignalChips(listing: Listing) {
  const chips: React.ReactNode[] = []
  const score = listing.score
  if (!score) return chips

  if (score.bmv_score >= 60)
    chips.push(<SignalChip key="bmv" variant="bmv" />)
  if (score.distress_score >= 50)
    chips.push(<SignalChip key="distress" variant="distress" />)
  if (score.regeneration_score >= 50)
    chips.push(<SignalChip key="regen" variant="regen" />)
  if (score.planning_score >= 50)
    chips.push(<SignalChip key="planning" variant="planning" />)
  if (listing.price_reduction_count > 0)
    chips.push(<SignalChip key="reduced" variant="reduced" />)
  return chips
}

export default function ListingsPage() {
  const [listings, setListings] = useState<Listing[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [filters, setFilters] = useState<Record<string, string>>({
    q: '',
    council: '',
    property_type: '',
    min_price: '',
    max_price: '',
    min_score: '',
    price_reduced: '',
  })
  const [applied, setApplied] = useState<Record<string, string>>(filters)

  const fetchListings = useCallback(
    async (f: Record<string, string>, p: number) => {
      setLoading(true)
      setError(null)
      const params: Record<string, string> = {
        limit: String(PAGE_SIZE),
        offset: String(p * PAGE_SIZE),
      }
      if (f.q) params.q = f.q
      if (f.council) params.council = f.council
      if (f.property_type) params.property_type = f.property_type
      if (f.min_price) params.min_price = f.min_price
      if (f.max_price) params.max_price = f.max_price
      if (f.min_score) params.min_score = f.min_score
      if (f.price_reduced === '1') params.price_reduced = '1'

      try {
        const data = await api.listings.list(params)
        setListings(data.items)
        setTotal(data.total)
      } catch (err: unknown) {
        setError(err instanceof Error ? err.message : 'Failed to load listings')
      } finally {
        setLoading(false)
      }
    },
    []
  )

  useEffect(() => {
    fetchListings(applied, page)
  }, [applied, page, fetchListings])

  function handleFilterChange(key: string, value: string) {
    setFilters((prev) => ({ ...prev, [key]: value }))
  }

  function handleSubmit() {
    setPage(0)
    setApplied(filters)
  }

  function handleReset() {
    const empty: Record<string, string> = {
      q: '',
      council: '',
      property_type: '',
      min_price: '',
      max_price: '',
      min_score: '',
      price_reduced: '',
    }
    setFilters(empty)
    setPage(0)
    setApplied(empty)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '20px' }}>
        <h1
          style={{
            fontSize: '1.4rem',
            fontWeight: 700,
            color: '#f1f5f9',
            letterSpacing: '-0.02em',
            marginBottom: '4px',
          }}
        >
          Deal Intelligence Feed
        </h1>
        <p style={{ fontSize: '0.82rem', color: '#64748b' }}>
          {total > 0 ? `${total.toLocaleString()} listings tracked across all NE councils` : 'Searching…'}
        </p>
      </div>

      {/* Filter bar */}
      <FilterBar
        fields={[
          {
            key: 'q',
            type: 'text',
            label: 'Keyword',
            placeholder: 'address, postcode…',
            width: '180px',
          },
          {
            key: 'council',
            type: 'select',
            label: 'Council',
            placeholder: 'All Councils',
            options: COUNCILS.map((c) => ({ value: c, label: c.replace(' Council', '').replace(' City', '').replace(' Borough', '').replace(' County', '') })),
          },
          {
            key: 'property_type',
            type: 'select',
            label: 'Type',
            placeholder: 'All Types',
            options: PROPERTY_TYPES,
            width: '120px',
          },
          {
            key: 'min_price',
            type: 'number',
            label: 'Min Price',
            placeholder: '£0',
            width: '90px',
          },
          {
            key: 'max_price',
            type: 'number',
            label: 'Max Price',
            placeholder: 'Any',
            width: '90px',
          },
          {
            key: 'min_score',
            type: 'select',
            label: 'Min Score',
            placeholder: 'Any Score',
            options: [
              { value: '50', label: '50+' },
              { value: '70', label: '70+' },
              { value: '85', label: '85+' },
            ],
            width: '110px',
          },
        ]}
        values={filters}
        onChange={handleFilterChange}
        onSubmit={handleSubmit}
        onReset={handleReset}
        loading={loading}
        extras={
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: '4px',
            }}
          >
            <label
              style={{
                fontSize: '0.68rem',
                fontWeight: 500,
                color: '#64748b',
                letterSpacing: '0.04em',
                textTransform: 'uppercase',
              }}
            >
              Price Reduced
            </label>
            <label
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={filters.price_reduced === '1'}
                onChange={(e) =>
                  handleFilterChange('price_reduced', e.target.checked ? '1' : '')
                }
                style={{ accentColor: '#2563eb', width: '14px', height: '14px', cursor: 'pointer' }}
              />
              <span style={{ fontSize: '0.82rem', color: '#94a3b8' }}>Only</span>
            </label>
          </div>
        }
      />

      {error && (
        <div
          style={{
            backgroundColor: 'rgba(185,28,28,0.08)',
            border: '1px solid rgba(239,68,68,0.2)',
            borderRadius: '4px',
            padding: '12px 16px',
            color: '#fca5a5',
            fontSize: '0.85rem',
            marginBottom: '12px',
          }}
        >
          {error}
        </div>
      )}

      {/* Table */}
      <div
        style={{
          backgroundColor: '#0f1729',
          border: '1px solid #1e2d45',
          borderRadius: '4px',
          overflow: 'hidden',
        }}
      >
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '960px' }}>
            <thead>
              <tr style={{ backgroundColor: '#0f1729' }}>
                {[
                  'Address',
                  'Council',
                  'Type',
                  'Price',
                  'Est. Value',
                  'Discount',
                  'Score',
                  'Signals',
                  'DOM',
                  '',
                ].map((h) => (
                  <th
                    key={h}
                    style={{
                      padding: '9px 14px',
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
                ? Array.from({ length: 10 }).map((_, i) => (
                    <tr key={i}>
                      {Array.from({ length: 10 }).map((_, j) => (
                        <td key={j} style={{ padding: '10px 14px' }}>
                          <div
                            style={{
                              height: '11px',
                              backgroundColor: '#1e2d45',
                              borderRadius: '2px',
                              opacity: 0.4,
                              width: j === 0 ? '160px' : j === 7 ? '80px' : '60px',
                            }}
                          />
                        </td>
                      ))}
                    </tr>
                  ))
                : listings.map((listing) => {
                    const score = listing.score
                    const discountPct = score?.discount_pct
                    const estValue = score?.estimated_fair_value
                    const signals = getSignalChips(listing)

                    return (
                      <tr
                        key={listing.id}
                        style={{
                          borderBottom: '1px solid #1e2d45',
                          transition: 'background-color 0.1s',
                        }}
                      >
                        <td style={{ padding: '8px 14px' }}>
                          <div
                            style={{
                              fontSize: '0.82rem',
                              color: '#e2e8f0',
                              fontWeight: 500,
                              maxWidth: '220px',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              whiteSpace: 'nowrap',
                            }}
                          >
                            {listing.address}
                          </div>
                          <div style={{ fontSize: '0.72rem', color: '#475569' }}>
                            {listing.postcode}
                          </div>
                        </td>
                        <td
                          style={{
                            padding: '8px 14px',
                            fontSize: '0.78rem',
                            color: '#64748b',
                            maxWidth: '140px',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {listing.council ?? '—'}
                        </td>
                        <td
                          style={{
                            padding: '8px 14px',
                            fontSize: '0.78rem',
                            color: '#64748b',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {propertyTypeLabel(listing.property_type)}
                          {listing.bedrooms ? ` · ${listing.bedrooms}bd` : ''}
                        </td>
                        <td
                          style={{
                            padding: '8px 14px',
                            fontSize: '0.82rem',
                            color: '#e2e8f0',
                            fontFamily: 'monospace',
                            fontWeight: 500,
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {formatPrice(listing.asking_price)}
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
                          {estValue ? formatPrice(estValue) : <span style={{ color: '#334155' }}>—</span>}
                        </td>
                        <td style={{ padding: '8px 14px', whiteSpace: 'nowrap' }}>
                          {discountPct != null ? (
                            <span
                              style={{
                                fontSize: '0.8rem',
                                fontWeight: 600,
                                color: discountPct < 0 ? '#10b981' : '#ef4444',
                                fontFamily: 'monospace',
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '3px',
                              }}
                            >
                              {discountPct < 0 ? '▼' : '▲'}{' '}
                              {Math.abs(discountPct).toFixed(1)}%
                            </span>
                          ) : (
                            <span style={{ color: '#334155', fontSize: '0.8rem' }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: '8px 14px' }}>
                          {score ? (
                            <ScoreBadge score={score.overall_score} />
                          ) : (
                            <span
                              style={{
                                fontSize: '0.72rem',
                                color: '#334155',
                                fontStyle: 'italic',
                              }}
                            >
                              Pending
                            </span>
                          )}
                        </td>
                        <td style={{ padding: '8px 14px' }}>
                          <div style={{ display: 'flex', gap: '3px', flexWrap: 'wrap' }}>
                            {signals.length > 0 ? signals : <span style={{ color: '#334155', fontSize: '0.75rem' }}>—</span>}
                          </div>
                        </td>
                        <td
                          style={{
                            padding: '8px 14px',
                            fontSize: '0.78rem',
                            color:
                              (listing.days_on_market ?? 0) > 60
                                ? '#d97706'
                                : '#64748b',
                            fontFamily: 'monospace',
                            whiteSpace: 'nowrap',
                          }}
                        >
                          {listing.days_on_market != null
                            ? `${listing.days_on_market}d`
                            : '—'}
                        </td>
                        <td style={{ padding: '8px 14px' }}>
                          <Link
                            href={`/listings/${listing.id}`}
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '4px',
                              fontSize: '0.75rem',
                              color: '#2563eb',
                              textDecoration: 'none',
                              border: '1px solid #1e3a8a',
                              borderRadius: '3px',
                              padding: '3px 8px',
                              whiteSpace: 'nowrap',
                              backgroundColor: 'rgba(37,99,235,0.06)',
                            }}
                          >
                            View <ArrowUpRight size={10} />
                          </Link>
                        </td>
                      </tr>
                    )
                  })}
            </tbody>
          </table>

          {!loading && listings.length === 0 && (
            <div
              style={{
                padding: '48px',
                textAlign: 'center',
                color: '#475569',
                fontSize: '0.875rem',
              }}
            >
              No listings found matching your filters.
            </div>
          )}
        </div>

        {/* Pagination */}
        {total > PAGE_SIZE && (
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 16px',
              borderTop: '1px solid #1e2d45',
              backgroundColor: '#0f1729',
            }}
          >
            <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
              Page {page + 1} of {totalPages} &mdash;{' '}
              {total.toLocaleString()} listings
            </span>
            <div style={{ display: 'flex', gap: '6px' }}>
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0 || loading}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '5px 10px',
                  backgroundColor: 'transparent',
                  border: '1px solid #1e2d45',
                  borderRadius: '3px',
                  color: page === 0 ? '#334155' : '#94a3b8',
                  fontSize: '0.8rem',
                  cursor: page === 0 ? 'not-allowed' : 'pointer',
                }}
              >
                <ChevronLeft size={13} /> Prev
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1 || loading}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  padding: '5px 10px',
                  backgroundColor: 'transparent',
                  border: '1px solid #1e2d45',
                  borderRadius: '3px',
                  color: page >= totalPages - 1 ? '#334155' : '#94a3b8',
                  fontSize: '0.8rem',
                  cursor: page >= totalPages - 1 ? 'not-allowed' : 'pointer',
                }}
              >
                Next <ChevronRight size={13} />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
