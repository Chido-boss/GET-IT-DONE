export type SignalVariant = 'bmv' | 'distress' | 'regen' | 'planning' | 'reduced'

const VARIANT_STYLES: Record<SignalVariant, string> = {
  bmv: 'bg-blue-500/10 text-blue-400 border border-blue-500/20',
  distress: 'bg-amber-500/10 text-amber-400 border border-amber-500/20',
  regen: 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
  planning: 'bg-purple-500/10 text-purple-400 border border-purple-500/20',
  reduced: 'bg-red-500/10 text-red-400 border border-red-500/20',
}

const VARIANT_LABELS: Record<SignalVariant, string> = {
  bmv: 'BMV',
  distress: 'Distress',
  regen: 'Regen',
  planning: 'Planning',
  reduced: 'Reduced',
}

interface SignalChipProps {
  variant: SignalVariant
  label?: string
}

export function SignalChip({ variant, label }: SignalChipProps) {
  return (
    <span
      className={`inline-flex items-center px-1.5 py-0.5 rounded text-[0.67rem] font-semibold tracking-wide uppercase ${VARIANT_STYLES[variant]}`}
    >
      {label ?? VARIANT_LABELS[variant]}
    </span>
  )
}

export function signalFromString(s: string): SignalVariant | null {
  const lower = s.toLowerCase()
  if (lower.includes('bmv') || lower.includes('below market')) return 'bmv'
  if (lower.includes('distress') || lower.includes('probate') || lower.includes('repossess'))
    return 'distress'
  if (lower.includes('regen') || lower.includes('regeneration')) return 'regen'
  if (lower.includes('plan')) return 'planning'
  if (lower.includes('reduc') || lower.includes('price drop')) return 'reduced'
  return null
}
