import { TrendingUp, TrendingDown } from 'lucide-react'

interface StatCardProps {
  title: string
  value: string | number
  subtitle?: string
  trend?: number // positive = up, negative = down
  accent?: 'green' | 'amber' | 'blue' | 'red' | 'default'
}

const ACCENT_COLORS: Record<string, string> = {
  green: '#10b981',
  amber: '#d97706',
  blue: '#2563eb',
  red: '#ef4444',
  default: '#e2e8f0',
}

export function StatCard({ title, value, subtitle, trend, accent = 'default' }: StatCardProps) {
  const valueColor = ACCENT_COLORS[accent]

  return (
    <div
      style={{
        backgroundColor: '#0f1729',
        border: '1px solid #1e2d45',
        borderRadius: '4px',
        padding: '20px 24px',
      }}
    >
      <div
        style={{
          fontSize: '0.72rem',
          fontWeight: 600,
          letterSpacing: '0.08em',
          textTransform: 'uppercase',
          color: '#64748b',
          marginBottom: '10px',
        }}
      >
        {title}
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          gap: '10px',
          marginBottom: subtitle ? '6px' : 0,
        }}
      >
        <span
          style={{
            fontSize: '2rem',
            fontWeight: 700,
            color: valueColor,
            lineHeight: 1,
            letterSpacing: '-0.02em',
          }}
        >
          {value}
        </span>

        {trend !== undefined && (
          <span
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
              fontSize: '0.78rem',
              fontWeight: 500,
              color: trend >= 0 ? '#10b981' : '#ef4444',
              marginBottom: '2px',
            }}
          >
            {trend >= 0 ? <TrendingUp size={13} /> : <TrendingDown size={13} />}
            {Math.abs(trend)}%
          </span>
        )}
      </div>

      {subtitle && (
        <div style={{ fontSize: '0.78rem', color: '#475569' }}>{subtitle}</div>
      )}
    </div>
  )
}
