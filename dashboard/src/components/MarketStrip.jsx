import React from 'react'

function formatNumber(n) {
  if (n == null) return '—'
  return n.toLocaleString()
}

export default function MarketStrip({ signalCount, stockCount, confirmedCount }) {
  return (
    <div className="bg-card-secondary border-b border-border px-6 py-1.5">
      <div className="flex items-center justify-center">
        <div className="text-xs text-text-muted">
          <span className="font-mono font-medium text-rose-accent">{formatNumber(confirmedCount)}</span> confirmed movers
          <span className="mx-1.5 text-border">&middot;</span>
          <span className="font-mono font-medium text-text-secondary">{formatNumber(signalCount)}</span> total signals
          <span className="mx-1.5 text-border">&middot;</span>
          <span className="font-mono font-medium text-text-secondary">{formatNumber(stockCount)}</span> stocks scanned
        </div>
      </div>
    </div>
  )
}
