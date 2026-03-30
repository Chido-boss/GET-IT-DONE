'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'

type ImportResult = { imported?: number; failed?: number; error?: string } | null

export default function AdminPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [results, setResults] = useState<Record<string, ImportResult>>({})
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const [rescoring, setRescoring] = useState(false)

  useEffect(() => {
    const token = localStorage.getItem('nb_token')
    if (!token) { router.push('/login'); return }
    const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    fetch(`${BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(u => {
        if (!u.is_admin) router.push('/dashboard')
        else setUser(u)
      })
  }, [router])

  async function handleUpload(type: string, file: File) {
    setLoading(l => ({ ...l, [type]: true }))
    setResults(r => ({ ...r, [type]: null }))
    const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await fetch(`${BASE}/imports/${type}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${localStorage.getItem('nb_token')}` },
        body: form
      })
      const data = await res.json()
      setResults(r => ({ ...r, [type]: res.ok ? data : { error: data.detail || 'Upload failed' } }))
    } catch (e: any) {
      setResults(r => ({ ...r, [type]: { error: e.message } }))
    } finally {
      setLoading(l => ({ ...l, [type]: false }))
    }
  }

  async function triggerRescore() {
    setRescoring(true)
    const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    await fetch(`${BASE}/imports/rescore`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${localStorage.getItem('nb_token')}` }
    })
    setTimeout(() => setRescoring(false), 2000)
  }

  if (!user) return null

  const importSections = [
    {
      key: 'listings',
      title: 'Property Listings CSV',
      description: 'Upload listings from any source. Required columns: address, postcode, asking_price. Optional: title, council, property_type, bedrooms, description, url, agent_name, source.',
      accept: '.csv'
    },
    {
      key: 'comparables',
      title: 'Land Registry Sold Prices',
      description: 'Upload Land Registry Price Paid CSV. Standard LR format supported: Transaction unique identifier, Price, Date of Transfer, Postcode, Property Type, PAON, Street, Town/City, District, County.',
      accept: '.csv'
    },
    {
      key: 'planning',
      title: 'Planning Applications CSV',
      description: 'Upload planning application data. Required: council, application_reference, address. Optional: postcode, application_type, proposal, status, date_received, url.',
      accept: '.csv'
    },
  ]

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 700, color: '#e2e8f0' }}>Admin — Data Import</h1>
        <p style={{ color: '#64748b', fontSize: 14, marginTop: 4 }}>
          Upload CSV data to populate the intelligence platform
        </p>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {importSections.map(section => (
          <div key={section.key} style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 22 }}>
            <h3 style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', marginBottom: 6 }}>{section.title}</h3>
            <p style={{ fontSize: 13, color: '#64748b', marginBottom: 16, lineHeight: 1.6 }}>{section.description}</p>
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <label style={{
                padding: '8px 16px', background: '#162035', border: '1px solid #1e2d45',
                borderRadius: 4, color: '#94a3b8', cursor: 'pointer', fontSize: 13
              }}>
                Choose CSV file
                <input
                  type="file"
                  accept={section.accept}
                  style={{ display: 'none' }}
                  onChange={e => {
                    const f = e.target.files?.[0]
                    if (f) handleUpload(section.key, f)
                    e.target.value = ''
                  }}
                />
              </label>
              {loading[section.key] && (
                <span style={{ fontSize: 13, color: '#64748b' }}>Uploading...</span>
              )}
              {results[section.key] && (
                results[section.key]?.error ? (
                  <span style={{ fontSize: 13, color: '#ef4444' }}>
                    ✕ {results[section.key]?.error}
                  </span>
                ) : (
                  <span style={{ fontSize: 13, color: '#10b981' }}>
                    ✓ {results[section.key]?.imported} imported
                    {(results[section.key]?.failed || 0) > 0 && `, ${results[section.key]?.failed} failed`}
                  </span>
                )
              )}
            </div>
          </div>
        ))}

        {/* Rescore */}
        <div style={{ background: '#0f1729', border: '1px solid #1e2d45', borderRadius: 6, padding: 22 }}>
          <h3 style={{ fontSize: 15, fontWeight: 600, color: '#e2e8f0', marginBottom: 6 }}>Rescore All Listings</h3>
          <p style={{ fontSize: 13, color: '#64748b', marginBottom: 16 }}>
            Recalculate BMV, distress, planning, and regeneration scores for all active listings.
            Run after importing new comparables or planning data.
          </p>
          <button
            onClick={triggerRescore}
            disabled={rescoring}
            style={{
              padding: '8px 18px', background: rescoring ? '#162035' : '#1d4ed8',
              color: 'white', border: 'none', borderRadius: 4, cursor: rescoring ? 'default' : 'pointer', fontSize: 13
            }}
          >
            {rescoring ? '⟳ Rescoring...' : '↻ Trigger Rescore'}
          </button>
        </div>
      </div>
    </div>
  )
}
