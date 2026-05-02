import React from 'react'
import { formatPrice, formatPct, getCatalystClass } from '../lib/format.js'

export default function WatchlistTable({ watchlist }) {
  if (!watchlist || watchlist.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-text-muted text-sm">
        <div className="text-center">
          <div className="text-3xl mb-2 opacity-30">&#9734;</div>
          <div>No watchlist entries yet</div>
          <div className="text-xs mt-1">Select a stock and click "+ Watchlist" to add one</div>
        </div>
      </div>
    )
  }

  return (
    <div className="overflow-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="px-3 py-2 text-xs font-medium text-text-muted">Stock</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right">Entry</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right">Current</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right">P&L</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-center">Type</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right">Days</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-center">Signal</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted">Status</th>
          </tr>
        </thead>
        <tbody>
          {watchlist.map((item, i) => {
            const pnl = item.current_price && item.entry_price
              ? (item.current_price - item.entry_price) / item.entry_price
              : null

            return (
              <tr key={item.ticker || i} className="border-b border-border/60 row-hover cursor-default">
                <td className="px-3 py-2.5">
                  <span className="font-mono font-semibold text-text-primary">{item.ticker}</span>
                  <div className="text-xs text-text-muted">{item.company_name || item.name || ''}</div>
                </td>
                <td className="px-3 py-2.5 text-right font-mono font-medium text-text-primary">
                  {formatPrice(item.entry_price)}
                </td>
                <td className="px-3 py-2.5 text-right font-mono font-medium text-text-primary">
                  {formatPrice(item.current_price)}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <span className={`font-mono font-bold ${
                    (pnl ?? 0) >= 0 ? 'text-up-green' : 'text-down-red'
                  }`}>
                    {pnl != null ? formatPct(pnl) : '—'}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-center">
                  <span className={`inline-flex items-center justify-center w-6 h-6 rounded-md text-xs font-bold ${
                    item.trade_type === 'A'
                      ? 'bg-rose-light text-rose-accent'
                      : 'bg-vol-amber-bg text-vol-amber'
                  }`}>
                    {item.trade_type || '—'}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-right font-mono text-text-secondary text-xs">
                  {item.days_held ?? '—'}
                </td>
                <td className="px-3 py-2.5 text-center">
                  <span className={getCatalystClass(item.catalyst_classification)}>
                    {(item.catalyst_classification || 'NONE').toUpperCase()}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className={`text-xs font-medium ${
                    item.status === 'In Position' ? 'text-up-green' :
                    item.status === 'Watching' ? 'text-vol-amber' :
                    item.status === 'Exited' ? 'text-text-muted' :
                    'text-text-secondary'
                  }`}>
                    {item.status || 'Watching'}
                  </span>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
