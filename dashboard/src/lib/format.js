export function formatPrice(n) {
  if (n == null) return '—'
  if (n < 0.01) return `$${n.toFixed(4)}`
  if (n < 1) return `$${n.toFixed(3)}`
  return `$${n.toFixed(2)}`
}

export function formatPct(n) {
  if (n == null) return '—'
  const pct = (n * 100)
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

export function formatMarketCap(n) {
  if (n == null || n === 0) return '—'
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`
  if (n >= 1_000_000) return `$${Math.round(n / 1_000_000)}M`
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`
  return `$${n}`
}

export function formatVolRatio(n) {
  if (n == null) return '—'
  return `${n.toFixed(1)}x`
}

export function getScoreColor(score) {
  if (score >= 80) return 'text-rose-accent font-bold'
  if (score >= 60) return 'text-rose-accent/80 font-semibold'
  return 'text-text-secondary'
}

export function getScoreFillColor(score) {
  if (score >= 80) return '#C25A62'
  if (score >= 60) return '#d4828a'
  return '#8C8680'
}

export function getCatalystClass(classification) {
  switch (classification?.toUpperCase()) {
    case 'GREEN': return 'catalyst-green'
    case 'YELLOW': return 'catalyst-yellow'
    case 'RED': return 'catalyst-red'
    default: return 'catalyst-none'
  }
}

export function timeAgo(dateString) {
  if (!dateString) return ''
  if (/^\d{9,10}$/.test(String(dateString))) {
    return timeAgo(new Date(parseInt(dateString) * 1000).toISOString())
  }
  const date = new Date(dateString)
  if (isNaN(date.getTime())) return ''
  const now = new Date()
  const diffMs = now - date
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 30) return `${diffDays}d ago`
  if (diffDays < 365) return `${Math.floor(diffDays / 30)}mo ago`
  return `${Math.floor(diffDays / 365)}y ago`
}
