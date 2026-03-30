import { formatDistanceToNow, parseISO } from 'date-fns'

export function formatPrice(p: number): string {
  return new Intl.NumberFormat('en-GB', {
    style: 'currency',
    currency: 'GBP',
    maximumFractionDigits: 0,
  }).format(p)
}

export function formatDiscount(pct: number): string {
  const sign = pct < 0 ? '' : '+'
  return `${sign}${pct.toFixed(1)}%`
}

export function scoreColor(score: number): string {
  if (score >= 70) return 'text-emerald-400'
  if (score >= 50) return 'text-amber-400'
  return 'text-slate-400'
}

export function scoreBgColor(score: number): string {
  if (score >= 70) return 'bg-emerald-400/10 text-emerald-400 border-emerald-400/20'
  if (score >= 50) return 'bg-amber-400/10 text-amber-400 border-amber-400/20'
  return 'bg-slate-400/10 text-slate-400 border-slate-400/20'
}

export function propertyTypeLabel(type: string): string {
  const map: Record<string, string> = {
    D: 'Detached',
    S: 'Semi-Detached',
    T: 'Terraced',
    F: 'Flat',
    O: 'Other',
    C: 'Commercial',
  }
  return map[type?.toUpperCase()] ?? type ?? 'Unknown'
}

export function councilShort(council: string): string {
  return council
    .replace('Metropolitan Borough Council', 'MBC')
    .replace('Borough Council', 'BC')
    .replace('District Council', 'DC')
    .replace('City Council', 'CC')
    .replace('County Council', 'CC')
    .replace('Council', '')
    .trim()
}

export function relativeDate(dateStr: string): string {
  try {
    return formatDistanceToNow(parseISO(dateStr), { addSuffix: true })
  } catch {
    return dateStr
  }
}

export function clsx(...classes: (string | undefined | null | false)[]): string {
  return classes.filter(Boolean).join(' ')
}
