import type { User, Listing, PlanningApplication, DashboardStats, AlertEvent, RegenZone } from '@/types'

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('nb_token') : null
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      fetchAPI<{ access_token: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    me: () => fetchAPI<User>('/auth/me'),
  },
  listings: {
    list: (params?: Record<string, string>) =>
      fetchAPI<{ items: Listing[]; total: number }>(
        `/listings?${new URLSearchParams(params)}`
      ),
    get: (id: string) => fetchAPI<Listing>(`/listings/${id}`),
  },
  planning: {
    list: (params?: Record<string, string>) =>
      fetchAPI<{ items: PlanningApplication[]; total: number }>(
        `/planning?${new URLSearchParams(params)}`
      ),
    get: (id: string) => fetchAPI<PlanningApplication>(`/planning/${id}`),
  },
  dashboard: {
    stats: () => fetchAPI<DashboardStats>('/dashboard/stats'),
  },
  alerts: {
    events: () => fetchAPI<AlertEvent[]>('/alerts/events'),
  },
  regenZones: {
    list: () => fetchAPI<RegenZone[]>('/regen-zones'),
  },
}
