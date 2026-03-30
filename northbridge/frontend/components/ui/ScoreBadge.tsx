export function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 70
      ? 'text-emerald-400 bg-emerald-400/10 border border-emerald-400/20'
      : score >= 50
      ? 'text-amber-400 bg-amber-400/10 border border-amber-400/20'
      : 'text-slate-400 bg-slate-400/10 border border-slate-400/20'
  return (
    <span
      className={`inline-flex items-center justify-center min-w-[36px] px-2 py-0.5 rounded text-xs font-bold ${color}`}
    >
      {score.toFixed(0)}
    </span>
  )
}
