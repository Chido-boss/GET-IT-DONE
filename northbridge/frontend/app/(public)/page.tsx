'use client'

import Link from 'next/link'
import { useState } from 'react'
import {
  BarChart2,
  FileText,
  MapPin,
  TrendingDown,
  Shield,
  ChevronRight,
  Check,
  ArrowUpRight,
} from 'lucide-react'

const MOCK_DEALS = [
  {
    address: '14 Bensham Road, Gateshead',
    postcode: 'NE8 1PA',
    price: 67500,
    estValue: 81200,
    discount: -16.9,
    score: 84,
    signals: ['Distress', 'BMV'],
  },
  {
    address: '37 Hylton Road, Sunderland',
    postcode: 'SR4 7AE',
    price: 54000,
    estValue: 63800,
    discount: -15.4,
    score: 78,
    signals: ['BMV', 'Reduced'],
  },
  {
    address: '9 Hartington Street, Hartlepool',
    postcode: 'TS24 0BQ',
    price: 39950,
    estValue: 47500,
    discount: -15.9,
    score: 76,
    signals: ['Distress', 'BMV', 'Regen'],
  },
  {
    address: '22 Westgate Road, Newcastle',
    postcode: 'NE4 6AP',
    price: 112000,
    estValue: 131000,
    discount: -14.5,
    score: 71,
    signals: ['BMV', 'Planning'],
  },
  {
    address: '58 Durham Road, Stockton-on-Tees',
    postcode: 'TS19 0DB',
    price: 79000,
    estValue: 91500,
    discount: -13.7,
    score: 68,
    signals: ['BMV', 'Regen'],
  },
]

function formatGBP(n: number) {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    maximumFractionDigits: 0,
  }).format(n)
}

const SIGNAL_COLORS: Record<string, string> = {
  BMV: 'bg-blue-500/15 text-blue-400 border border-blue-500/25',
  Distress: 'bg-amber-500/15 text-amber-400 border border-amber-500/25',
  Regen: 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25',
  Planning: 'bg-purple-500/15 text-purple-400 border border-purple-500/25',
  Reduced: 'bg-red-500/15 text-red-400 border border-red-500/25',
}

export default function LandingPage() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)

  function handleRequest(e: React.FormEvent) {
    e.preventDefault()
    setSubmitted(true)
  }

  return (
    <div style={{ backgroundColor: '#090e1a', color: '#e2e8f0', minHeight: '100vh' }}>
      {/* ── NAVBAR ── */}
      <nav
        style={{
          borderBottom: '1px solid #1e2d45',
          backgroundColor: 'rgba(9,14,26,0.96)',
          backdropFilter: 'blur(8px)',
          position: 'sticky',
          top: 0,
          zIndex: 50,
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            padding: '0 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            height: '58px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div
              style={{
                width: '28px',
                height: '28px',
                backgroundColor: '#1d4ed8',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                borderRadius: '3px',
              }}
            >
              <BarChart2 size={16} color="#fff" />
            </div>
            <span style={{ fontWeight: 700, fontSize: '1rem', letterSpacing: '-0.01em' }}>
              Northbridge{' '}
              <span style={{ color: '#d97706', fontWeight: 700 }}>Intelligence</span>
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '32px' }}>
            <div
              style={{
                display: 'flex',
                gap: '24px',
                fontSize: '0.875rem',
                color: '#94a3b8',
              }}
            >
              <a href="#features" style={{ color: 'inherit', textDecoration: 'none' }}>
                Features
              </a>
              <a href="#pricing" style={{ color: 'inherit', textDecoration: 'none' }}>
                Pricing
              </a>
              <a href="#access" style={{ color: 'inherit', textDecoration: 'none' }}>
                Request Access
              </a>
            </div>
            <Link
              href="/login"
              style={{
                backgroundColor: '#1d4ed8',
                color: '#fff',
                padding: '7px 16px',
                borderRadius: '4px',
                fontSize: '0.875rem',
                fontWeight: 500,
                textDecoration: 'none',
                border: '1px solid #2563eb',
              }}
            >
              Sign In
            </Link>
          </div>
        </div>
      </nav>

      {/* ── HERO ── */}
      <section
        style={{
          borderBottom: '1px solid #1e2d45',
          padding: '96px 24px 80px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Subtle grid background */}
        <div
          style={{
            position: 'absolute',
            inset: 0,
            backgroundImage:
              'linear-gradient(rgba(30,45,69,0.2) 1px, transparent 1px), linear-gradient(90deg, rgba(30,45,69,0.2) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background:
              'radial-gradient(ellipse 80% 50% at 50% -10%, rgba(29,78,216,0.12) 0%, transparent 60%)',
            pointerEvents: 'none',
          }}
        />

        <div
          style={{
            maxWidth: '860px',
            margin: '0 auto',
            textAlign: 'center',
            position: 'relative',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '8px',
              backgroundColor: 'rgba(29,78,216,0.12)',
              border: '1px solid rgba(37,99,235,0.3)',
              borderRadius: '3px',
              padding: '5px 12px',
              marginBottom: '32px',
              fontSize: '0.75rem',
              color: '#93c5fd',
              fontWeight: 500,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            <span
              style={{
                width: '6px',
                height: '6px',
                backgroundColor: '#10b981',
                borderRadius: '50%',
                display: 'inline-block',
              }}
            />
            Early Access — Live Data
          </div>

          <h1
            style={{
              fontSize: 'clamp(2rem, 5vw, 3.25rem)',
              fontWeight: 800,
              lineHeight: 1.12,
              letterSpacing: '-0.025em',
              marginBottom: '24px',
              color: '#f1f5f9',
            }}
          >
            Find below-market property deals across{' '}
            <span
              style={{
                color: '#d97706',
                borderBottom: '2px solid #b45309',
                paddingBottom: '2px',
              }}
            >
              the North East.
            </span>{' '}
            Before anyone else does.
          </h1>

          <p
            style={{
              fontSize: '1.15rem',
              color: '#94a3b8',
              lineHeight: 1.7,
              marginBottom: '40px',
              maxWidth: '680px',
              margin: '0 auto 40px',
            }}
          >
            Northbridge Intelligence aggregates planning data, sold prices, and market
            signals across all North East councils — giving developers, investors, and
            planning consultants a serious edge in the most underserved property market in
            England.
          </p>

          <div
            style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'center',
              flexWrap: 'wrap',
              marginBottom: '48px',
            }}
          >
            <a
              href="#access"
              style={{
                backgroundColor: '#1d4ed8',
                color: '#fff',
                padding: '12px 28px',
                borderRadius: '4px',
                fontSize: '0.95rem',
                fontWeight: 600,
                textDecoration: 'none',
                border: '1px solid #2563eb',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
                transition: 'background-color 0.15s',
              }}
            >
              Request Early Access <ChevronRight size={16} />
            </a>
            <a
              href="#features"
              style={{
                backgroundColor: 'transparent',
                color: '#94a3b8',
                padding: '12px 28px',
                borderRadius: '4px',
                fontSize: '0.95rem',
                fontWeight: 500,
                textDecoration: 'none',
                border: '1px solid #1e2d45',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              See how it works
            </a>
          </div>

          <p
            style={{
              fontSize: '0.8rem',
              color: '#475569',
              letterSpacing: '0.04em',
            }}
          >
            Covering{' '}
            {[
              'Gateshead',
              'Newcastle',
              'Sunderland',
              'Durham',
              'Teesside',
              'Northumberland',
            ].map((c, i, arr) => (
              <span key={c}>
                <span style={{ color: '#64748b' }}>{c}</span>
                {i < arr.length - 1 && (
                  <span style={{ margin: '0 8px', color: '#1e2d45' }}>·</span>
                )}
              </span>
            ))}
          </p>
        </div>
      </section>

      {/* ── STATS BAR ── */}
      <section
        style={{
          borderBottom: '1px solid #1e2d45',
          backgroundColor: '#0f1729',
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            padding: '0 24px',
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
          }}
        >
          {[
            { value: '10', label: 'Councils Monitored', sub: 'All NE local authorities' },
            {
              value: 'HM Land',
              label: 'Registry Comparables',
              sub: 'Verified sold price data',
            },
            {
              value: '2,400+',
              label: 'Planning Apps Tracked',
              sub: 'Updated weekly',
            },
            {
              value: 'Daily',
              label: 'Deals Scored',
              sub: 'BMV · Distress · Uplift',
            },
          ].map((stat, i) => (
            <div
              key={i}
              style={{
                padding: '28px 24px',
                borderRight: i < 3 ? '1px solid #1e2d45' : undefined,
                textAlign: 'center',
              }}
            >
              <div
                style={{
                  fontSize: '1.75rem',
                  fontWeight: 700,
                  color: '#d97706',
                  letterSpacing: '-0.02em',
                  lineHeight: 1,
                  marginBottom: '6px',
                }}
              >
                {stat.value}
              </div>
              <div
                style={{
                  fontSize: '0.875rem',
                  color: '#e2e8f0',
                  fontWeight: 500,
                  marginBottom: '4px',
                }}
              >
                {stat.label}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#475569' }}>{stat.sub}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── FEATURES ── */}
      <section
        id="features"
        style={{
          borderBottom: '1px solid #1e2d45',
          padding: '80px 24px',
        }}
      >
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div style={{ marginBottom: '56px', maxWidth: '520px' }}>
            <div
              style={{
                fontSize: '0.7rem',
                fontWeight: 600,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: '#2563eb',
                marginBottom: '12px',
              }}
            >
              Platform Capabilities
            </div>
            <h2
              style={{
                fontSize: '2rem',
                fontWeight: 700,
                color: '#f1f5f9',
                letterSpacing: '-0.02em',
                marginBottom: '16px',
              }}
            >
              Intelligence built for serious operators
            </h2>
            <p style={{ color: '#64748b', lineHeight: 1.7 }}>
              Not a portal. Not a listing aggregator. A structured intelligence layer over
              the North East property market.
            </p>
          </div>

          <div
            style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1px', backgroundColor: '#1e2d45' }}
          >
            {[
              {
                icon: <TrendingDown size={22} color="#2563eb" />,
                title: 'Deal Intelligence',
                body: 'Every listing scored for BMV discount, distress signals, and market momentum. Understand why a deal is worth pursuing in seconds — not after three site visits.',
                points: [
                  'BMV discount vs Land Registry comps',
                  'Distress language detection',
                  'Days on market & reduction tracking',
                  'Composite confidence scoring',
                ],
              },
              {
                icon: <FileText size={22} color="#7c3aed" />,
                title: 'Planning Uplift',
                body: 'Track change-of-use applications, prior approvals, and conversion opportunities across all NE planning portals. Every application scored for value uplift potential.',
                points: [
                  'All 10 NE council portals aggregated',
                  'Prior approval & PD rights tracking',
                  'Uplift scoring per application',
                  'Weekly updates, email alerts',
                ],
              },
              {
                icon: <MapPin size={22} color="#10b981" />,
                title: 'Regeneration Edge',
                body: 'Northbridge maps every active and emerging regeneration zone — Teesworks, Quayside, Sunderland Riverside and more — so you position capital before the value lands.',
                points: [
                  'Active regen zone boundaries',
                  'Funding announcements tracked',
                  'Opportunity notes per zone',
                  'Postcode proximity scoring',
                ],
              },
            ].map((f, i) => (
              <div
                key={i}
                style={{
                  backgroundColor: '#090e1a',
                  padding: '40px 36px',
                }}
              >
                <div
                  style={{
                    width: '44px',
                    height: '44px',
                    backgroundColor: '#0f1729',
                    border: '1px solid #1e2d45',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: '24px',
                    borderRadius: '4px',
                  }}
                >
                  {f.icon}
                </div>
                <h3
                  style={{
                    fontSize: '1.1rem',
                    fontWeight: 600,
                    color: '#f1f5f9',
                    marginBottom: '12px',
                  }}
                >
                  {f.title}
                </h3>
                <p
                  style={{
                    color: '#64748b',
                    lineHeight: 1.7,
                    fontSize: '0.9rem',
                    marginBottom: '24px',
                  }}
                >
                  {f.body}
                </p>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {f.points.map((pt) => (
                    <li
                      key={pt}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                        fontSize: '0.82rem',
                        color: '#94a3b8',
                        marginBottom: '8px',
                      }}
                    >
                      <Check size={12} color="#10b981" strokeWidth={3} />
                      {pt}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── DEAL TABLE PREVIEW ── */}
      <section
        style={{
          borderBottom: '1px solid #1e2d45',
          padding: '80px 24px',
          backgroundColor: '#0f1729',
        }}
      >
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-end',
              justifyContent: 'space-between',
              marginBottom: '32px',
              flexWrap: 'wrap',
              gap: '16px',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: '0.7rem',
                  fontWeight: 600,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: '#2563eb',
                  marginBottom: '12px',
                }}
              >
                Live Deal Feed Preview
              </div>
              <h2
                style={{
                  fontSize: '1.75rem',
                  fontWeight: 700,
                  color: '#f1f5f9',
                  letterSpacing: '-0.02em',
                }}
              >
                What the intelligence feed looks like
              </h2>
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.8rem',
                color: '#10b981',
                backgroundColor: 'rgba(16,185,129,0.08)',
                border: '1px solid rgba(16,185,129,0.2)',
                borderRadius: '4px',
                padding: '6px 12px',
              }}
            >
              <span
                style={{
                  width: '6px',
                  height: '6px',
                  backgroundColor: '#10b981',
                  borderRadius: '50%',
                  display: 'inline-block',
                }}
              />
              Updated daily
            </div>
          </div>

          <div
            style={{
              border: '1px solid #1e2d45',
              borderRadius: '4px',
              overflow: 'hidden',
            }}
          >
            {/* Table header */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '2fr 1fr 1fr 1fr 80px 1fr',
                backgroundColor: '#0f1729',
                borderBottom: '1px solid #1e2d45',
                padding: '10px 16px',
                gap: '8px',
              }}
            >
              {['Address', 'Price', 'Est. Value', 'Discount', 'Score', 'Signals'].map(
                (h) => (
                  <div
                    key={h}
                    style={{
                      fontSize: '0.68rem',
                      fontWeight: 600,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      color: '#64748b',
                    }}
                  >
                    {h}
                  </div>
                )
              )}
            </div>

            {MOCK_DEALS.map((deal, i) => (
              <div
                key={i}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '2fr 1fr 1fr 1fr 80px 1fr',
                  padding: '12px 16px',
                  gap: '8px',
                  borderBottom: i < MOCK_DEALS.length - 1 ? '1px solid #1e2d45' : undefined,
                  alignItems: 'center',
                  backgroundColor: i % 2 === 0 ? 'transparent' : 'rgba(15,23,41,0.5)',
                }}
              >
                <div>
                  <div style={{ fontSize: '0.875rem', color: '#e2e8f0', fontWeight: 500 }}>
                    {deal.address}
                  </div>
                  <div style={{ fontSize: '0.75rem', color: '#475569' }}>
                    {deal.postcode}
                  </div>
                </div>
                <div style={{ fontSize: '0.875rem', color: '#e2e8f0', fontFamily: 'monospace' }}>
                  {formatGBP(deal.price)}
                </div>
                <div style={{ fontSize: '0.875rem', color: '#94a3b8', fontFamily: 'monospace' }}>
                  {formatGBP(deal.estValue)}
                </div>
                <div
                  style={{
                    fontSize: '0.875rem',
                    color: '#10b981',
                    fontFamily: 'monospace',
                    fontWeight: 600,
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                >
                  <span style={{ fontSize: '0.7rem' }}>▼</span>
                  {Math.abs(deal.discount)}%
                </div>
                <div>
                  <span
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      minWidth: '36px',
                      padding: '2px 7px',
                      borderRadius: '3px',
                      fontSize: '0.8rem',
                      fontWeight: 700,
                      ...(deal.score >= 70
                        ? {
                            backgroundColor: 'rgba(16,185,129,0.12)',
                            color: '#10b981',
                            border: '1px solid rgba(16,185,129,0.25)',
                          }
                        : deal.score >= 50
                        ? {
                            backgroundColor: 'rgba(217,119,6,0.12)',
                            color: '#d97706',
                            border: '1px solid rgba(217,119,6,0.25)',
                          }
                        : {
                            backgroundColor: 'rgba(100,116,139,0.12)',
                            color: '#94a3b8',
                            border: '1px solid rgba(100,116,139,0.2)',
                          }),
                    }}
                  >
                    {deal.score}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                  {deal.signals.map((sig) => (
                    <span
                      key={sig}
                      className={SIGNAL_COLORS[sig]}
                      style={{
                        fontSize: '0.68rem',
                        fontWeight: 600,
                        padding: '2px 6px',
                        borderRadius: '3px',
                        letterSpacing: '0.03em',
                      }}
                    >
                      {sig.toUpperCase()}
                    </span>
                  ))}
                </div>
              </div>
            ))}

            <div
              style={{
                padding: '12px 16px',
                backgroundColor: 'rgba(29,78,216,0.04)',
                borderTop: '1px solid #1e2d45',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
              }}
            >
              <span style={{ fontSize: '0.8rem', color: '#475569' }}>
                Showing 5 of 340+ deals tracked this week
              </span>
              <a
                href="#access"
                style={{
                  fontSize: '0.8rem',
                  color: '#2563eb',
                  textDecoration: 'none',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                }}
              >
                Get full access <ArrowUpRight size={13} />
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* ── PRICING ── */}
      <section id="pricing" style={{ borderBottom: '1px solid #1e2d45', padding: '80px 24px' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <div style={{ textAlign: 'center', marginBottom: '56px' }}>
            <div
              style={{
                fontSize: '0.7rem',
                fontWeight: 600,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: '#2563eb',
                marginBottom: '12px',
              }}
            >
              Pricing
            </div>
            <h2
              style={{
                fontSize: '2rem',
                fontWeight: 700,
                color: '#f1f5f9',
                letterSpacing: '-0.02em',
                marginBottom: '12px',
              }}
            >
              Serious intelligence. Transparent pricing.
            </h2>
            <p style={{ color: '#64748b', maxWidth: '500px', margin: '0 auto', lineHeight: 1.7 }}>
              No hidden fees. No long contracts. Cancel anytime. Prices designed for
              serious operators, not hobby investors.
            </p>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(3, 1fr)',
              gap: '1px',
              backgroundColor: '#1e2d45',
              border: '1px solid #1e2d45',
              borderRadius: '4px',
              overflow: 'hidden',
              marginBottom: '24px',
            }}
          >
            {[
              {
                tier: 'Investor',
                price: '£49',
                period: '/month',
                description: 'For individual property investors tracking deals across the North East.',
                highlight: false,
                features: [
                  'Full deals intelligence feed',
                  'BMV & distress scoring',
                  'Planning application feed',
                  'Regeneration zone mapping',
                  'Email deal alerts',
                  'Up to 20 saved searches',
                  'CSV export (monthly)',
                ],
              },
              {
                tier: 'Consultant',
                price: '£99',
                period: '/month',
                description: 'For planning consultants, agents, and active deal sourcers.',
                highlight: true,
                features: [
                  'Everything in Investor',
                  'Unlimited saved searches',
                  'Priority deal alerts',
                  'Full CSV & data export',
                  'Planning uplift analysis',
                  'Comparable sales deep-dive',
                  'Client report generation',
                ],
              },
              {
                tier: 'Developer',
                price: '£149–£299',
                period: '/month',
                description: 'For development companies, land teams, and institutional operators.',
                highlight: false,
                features: [
                  'Everything in Consultant',
                  'REST API access',
                  'Up to 5 team seats',
                  'Bespoke council coverage',
                  'Weekly briefing report',
                  'Dedicated account manager',
                  'Custom data integrations',
                ],
              },
            ].map((plan, i) => (
              <div
                key={i}
                style={{
                  backgroundColor: plan.highlight ? '#0f1729' : '#090e1a',
                  padding: '40px 32px',
                  position: 'relative',
                  borderTop: plan.highlight ? '2px solid #2563eb' : '2px solid transparent',
                }}
              >
                {plan.highlight && (
                  <div
                    style={{
                      position: 'absolute',
                      top: '-1px',
                      left: '50%',
                      transform: 'translateX(-50%)',
                      backgroundColor: '#2563eb',
                      color: '#fff',
                      fontSize: '0.65rem',
                      fontWeight: 700,
                      letterSpacing: '0.08em',
                      textTransform: 'uppercase',
                      padding: '3px 10px',
                      borderRadius: '0 0 4px 4px',
                    }}
                  >
                    Most Popular
                  </div>
                )}
                <div
                  style={{
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    color: '#64748b',
                    marginBottom: '16px',
                  }}
                >
                  {plan.tier}
                </div>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '4px', marginBottom: '8px' }}>
                  <span
                    style={{
                      fontSize: '2.25rem',
                      fontWeight: 800,
                      color: '#f1f5f9',
                      letterSpacing: '-0.03em',
                    }}
                  >
                    {plan.price}
                  </span>
                  <span style={{ color: '#64748b', fontSize: '0.875rem' }}>{plan.period}</span>
                </div>
                <p
                  style={{
                    color: '#64748b',
                    fontSize: '0.875rem',
                    lineHeight: 1.6,
                    marginBottom: '28px',
                    minHeight: '60px',
                  }}
                >
                  {plan.description}
                </p>
                <a
                  href="#access"
                  style={{
                    display: 'block',
                    textAlign: 'center',
                    padding: '10px 20px',
                    borderRadius: '4px',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    textDecoration: 'none',
                    marginBottom: '28px',
                    ...(plan.highlight
                      ? {
                          backgroundColor: '#1d4ed8',
                          color: '#fff',
                          border: '1px solid #2563eb',
                        }
                      : {
                          backgroundColor: 'transparent',
                          color: '#94a3b8',
                          border: '1px solid #1e2d45',
                        }),
                  }}
                >
                  Request Access
                </a>
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {plan.features.map((f) => (
                    <li
                      key={f}
                      style={{
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '10px',
                        fontSize: '0.82rem',
                        color: '#94a3b8',
                        marginBottom: '9px',
                      }}
                    >
                      <Check
                        size={13}
                        color={plan.highlight ? '#10b981' : '#475569'}
                        strokeWidth={2.5}
                        style={{ marginTop: '2px', flexShrink: 0 }}
                      />
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>

          <div
            style={{
              backgroundColor: '#0f1729',
              border: '1px solid #1e2d45',
              borderRadius: '4px',
              padding: '20px 28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '16px',
            }}
          >
            <div>
              <span style={{ fontSize: '0.875rem', color: '#e2e8f0', fontWeight: 500 }}>
                Enterprise &amp; Bespoke
              </span>
              <span
                style={{
                  fontSize: '0.875rem',
                  color: '#64748b',
                  marginLeft: '12px',
                }}
              >
                Large development companies, housing associations, or national investors
                requiring custom data feeds, SLA support, or white-label reporting.
              </span>
            </div>
            <a
              href="mailto:intelligence@northbridge.co.uk"
              style={{
                color: '#2563eb',
                fontSize: '0.875rem',
                fontWeight: 500,
                textDecoration: 'none',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                whiteSpace: 'nowrap',
              }}
            >
              Talk to us <ArrowUpRight size={14} />
            </a>
          </div>
        </div>
      </section>

      {/* ── ACCESS REQUEST CTA ── */}
      <section
        id="access"
        style={{
          borderBottom: '1px solid #1e2d45',
          padding: '96px 24px',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(ellipse 60% 60% at 50% 50%, rgba(29,78,216,0.08) 0%, transparent 70%)',
            pointerEvents: 'none',
          }}
        />
        <div
          style={{
            maxWidth: '600px',
            margin: '0 auto',
            textAlign: 'center',
            position: 'relative',
          }}
        >
          <div
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              backgroundColor: 'rgba(16,185,129,0.08)',
              border: '1px solid rgba(16,185,129,0.2)',
              borderRadius: '3px',
              padding: '5px 12px',
              marginBottom: '28px',
              fontSize: '0.75rem',
              color: '#10b981',
              fontWeight: 500,
            }}
          >
            <Shield size={12} />
            Built for the North East. Ready for the UK.
          </div>

          <h2
            style={{
              fontSize: 'clamp(1.75rem, 4vw, 2.5rem)',
              fontWeight: 800,
              color: '#f1f5f9',
              letterSpacing: '-0.025em',
              marginBottom: '16px',
              lineHeight: 1.2,
            }}
          >
            Northbridge Intelligence is live and in early access.
          </h2>
          <p
            style={{
              color: '#64748b',
              lineHeight: 1.7,
              marginBottom: '40px',
              fontSize: '1rem',
            }}
          >
            Request your account today. We&apos;re onboarding operators by application only
            during the early access period. Places are limited.
          </p>

          {submitted ? (
            <div
              style={{
                backgroundColor: 'rgba(16,185,129,0.08)',
                border: '1px solid rgba(16,185,129,0.25)',
                borderRadius: '4px',
                padding: '20px 24px',
                color: '#10b981',
                fontWeight: 500,
              }}
            >
              <Check
                size={20}
                style={{ marginBottom: '8px', display: 'block', margin: '0 auto 8px' }}
              />
              Request received. We&apos;ll be in touch within 48 hours.
            </div>
          ) : (
            <form
              onSubmit={handleRequest}
              style={{
                display: 'flex',
                gap: '8px',
                maxWidth: '440px',
                margin: '0 auto',
              }}
            >
              <input
                type="email"
                required
                placeholder="your@email.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{
                  flex: 1,
                  backgroundColor: '#0f1729',
                  border: '1px solid #1e2d45',
                  borderRadius: '4px',
                  padding: '11px 14px',
                  fontSize: '0.9rem',
                  color: '#e2e8f0',
                  outline: 'none',
                }}
              />
              <button
                type="submit"
                style={{
                  backgroundColor: '#1d4ed8',
                  color: '#fff',
                  border: '1px solid #2563eb',
                  borderRadius: '4px',
                  padding: '11px 22px',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                Request Access
              </button>
            </form>
          )}
          <p style={{ fontSize: '0.75rem', color: '#334155', marginTop: '16px' }}>
            No spam. No commitment. Professional enquiries only.
          </p>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer
        style={{
          backgroundColor: '#090e1a',
          borderTop: '1px solid #1e2d45',
          padding: '40px 24px',
        }}
      >
        <div
          style={{
            maxWidth: '1200px',
            margin: '0 auto',
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '24px',
          }}
        >
          <div style={{ maxWidth: '320px' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '12px',
              }}
            >
              <div
                style={{
                  width: '24px',
                  height: '24px',
                  backgroundColor: '#1d4ed8',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  borderRadius: '3px',
                }}
              >
                <BarChart2 size={13} color="#fff" />
              </div>
              <span style={{ fontWeight: 700, fontSize: '0.9rem' }}>
                Northbridge <span style={{ color: '#d97706' }}>Intelligence</span>
              </span>
            </div>
            <p style={{ fontSize: '0.82rem', color: '#475569', lineHeight: 1.6 }}>
              A serious property intelligence platform for the North East of England.
            </p>
          </div>

          <div
            style={{
              display: 'flex',
              gap: '32px',
              flexWrap: 'wrap',
              alignItems: 'center',
            }}
          >
            {['Privacy', 'Terms', 'Contact'].map((link) => (
              <a
                key={link}
                href="#"
                style={{
                  fontSize: '0.82rem',
                  color: '#475569',
                  textDecoration: 'none',
                }}
              >
                {link}
              </a>
            ))}
          </div>
        </div>

        <div
          style={{
            maxWidth: '1200px',
            margin: '24px auto 0',
            paddingTop: '24px',
            borderTop: '1px solid #1e2d45',
            fontSize: '0.78rem',
            color: '#334155',
          }}
        >
          &copy; 2026 Northbridge Capital Partners Ltd. All rights reserved. Company
          registered in England &amp; Wales.
        </div>
      </footer>
    </div>
  )
}
