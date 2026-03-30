'use client'

import { Search, X } from 'lucide-react'
import React from 'react'

export interface FilterField {
  key: string
  type: 'text' | 'select' | 'number'
  label: string
  placeholder?: string
  options?: Array<{ value: string; label: string }>
  width?: string
}

interface FilterBarProps {
  fields: FilterField[]
  values: Record<string, string>
  onChange: (key: string, value: string) => void
  onSubmit: () => void
  onReset: () => void
  loading?: boolean
  extras?: React.ReactNode
}

export function FilterBar({
  fields,
  values,
  onChange,
  onSubmit,
  onReset,
  loading,
  extras,
}: FilterBarProps) {
  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    onSubmit()
  }

  return (
    <form
      onSubmit={handleSubmit}
      style={{
        backgroundColor: '#0f1729',
        border: '1px solid #1e2d45',
        borderRadius: '4px',
        padding: '14px 16px',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '8px',
        alignItems: 'flex-end',
        marginBottom: '16px',
      }}
    >
      {fields.map((field) => (
        <div key={field.key} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          <label
            style={{
              fontSize: '0.68rem',
              fontWeight: 500,
              color: '#64748b',
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            {field.label}
          </label>
          {field.type === 'select' ? (
            <select
              value={values[field.key] ?? ''}
              onChange={(e) => onChange(field.key, e.target.value)}
              style={{
                backgroundColor: '#090e1a',
                border: '1px solid #1e2d45',
                borderRadius: '3px',
                padding: '6px 10px',
                fontSize: '0.82rem',
                color: values[field.key] ? '#e2e8f0' : '#64748b',
                outline: 'none',
                width: field.width ?? '140px',
                cursor: 'pointer',
              }}
            >
              <option value="">{field.placeholder ?? `All`}</option>
              {field.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          ) : (
            <div style={{ position: 'relative' }}>
              {field.type === 'text' && (
                <Search
                  size={13}
                  style={{
                    position: 'absolute',
                    left: '8px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    color: '#475569',
                    pointerEvents: 'none',
                  }}
                />
              )}
              <input
                type={field.type === 'number' ? 'number' : 'text'}
                value={values[field.key] ?? ''}
                onChange={(e) => onChange(field.key, e.target.value)}
                placeholder={field.placeholder}
                style={{
                  backgroundColor: '#090e1a',
                  border: '1px solid #1e2d45',
                  borderRadius: '3px',
                  padding: field.type === 'text' ? '6px 10px 6px 26px' : '6px 10px',
                  fontSize: '0.82rem',
                  color: '#e2e8f0',
                  outline: 'none',
                  width: field.width ?? (field.type === 'text' ? '180px' : '100px'),
                }}
              />
            </div>
          )}
        </div>
      ))}

      {extras}

      <div style={{ display: 'flex', gap: '6px', marginLeft: 'auto', alignItems: 'flex-end' }}>
        <button
          type="submit"
          disabled={loading}
          style={{
            backgroundColor: '#1d4ed8',
            color: '#fff',
            border: '1px solid #2563eb',
            borderRadius: '3px',
            padding: '6px 16px',
            fontSize: '0.82rem',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
            opacity: loading ? 0.6 : 1,
          }}
        >
          {loading ? 'Loading…' : 'Filter'}
        </button>
        <button
          type="button"
          onClick={onReset}
          style={{
            backgroundColor: 'transparent',
            color: '#64748b',
            border: '1px solid #1e2d45',
            borderRadius: '3px',
            padding: '6px 12px',
            fontSize: '0.82rem',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '4px',
          }}
        >
          <X size={12} /> Reset
        </button>
      </div>
    </form>
  )
}
