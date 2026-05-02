import React from 'react'
import Sparkline from './Sparkline.jsx'
import {
  formatPrice,
  formatPct,
  formatMarketCap,
  formatVolRatio,
  getScoreColor,
  getScoreFillColor,
  getCatalystClass,
  timeAgo,
} from '../lib/format.js'

function getMove(stock, activePeriod) {
  switch (activePeriod) {
    case 'today': return stock.pct_move_1d
    case 'week': return stock.pct_move_5d
    case 'month': return stock.pct_move_10d
    default: return stock.pct_move_1d
  }
}

function getSignalPills(stock) {
  const pills = []
  if ((stock.pct_move_10d ?? 0) >= 0.30) pills.push('Breakout')
  if ((stock.vol_ratio ?? 0) >= 5) pills.push('Vol Surge')
  if (stock.near_52w_high) pills.push('New High')
  return pills
}

function sortSignals(signals, sortBy, activePeriod) {
  const sorted = [...signals]
  sorted.sort((a, b) => {
    switch (sortBy) {
      case 'score': return (b.momentum_score ?? 0) - (a.momentum_score ?? 0)
      case 'move': return (getMove(b, activePeriod) ?? 0) - (getMove(a, activePeriod) ?? 0)
      case 'volume': return (b.vol_ratio ?? 0) - (a.vol_ratio ?? 0)
      case 'cap': return (b.market_cap ?? 0) - (a.market_cap ?? 0)
      case 'conviction': return (b.conviction_score ?? 0) - (a.conviction_score ?? 0)
      case 'newest': {
        const aDate = a.news_date ? new Date(a.news_date).getTime() : 0
        const bDate = b.news_date ? new Date(b.news_date).getTime() : 0
        // Stocks without news go to bottom
        if (aDate && !bDate) return -1
        if (!aDate && bDate) return 1
        return bDate - aDate
      }
      default: return 0
    }
  })
  return sorted
}

function filterSignals(signals, filterCatalyst) {
  if (filterCatalyst === 'all') return signals
  return signals.filter(s => (s.catalyst_classification || '').toUpperCase() === filterCatalyst)
}

// GICS sector names as returned by yfinance
const KNOWN_SECTORS = new Set([
  'Basic Materials', 'Energy', 'Industrials', 'Consumer Cyclical',
  'Consumer Defensive', 'Healthcare', 'Financial Services', 'Technology',
  'Communication Services', 'Real Estate', 'Utilities',
])

function filterBySector(signals, excludeSectors) {
  if (!excludeSectors || excludeSectors.size === 0) return signals
  return signals.filter(s => {
    const raw = s.sector || 'Other'
    const sector = KNOWN_SECTORS.has(raw) ? raw : 'Other'
    return !excludeSectors.has(sector)
  })
}

export default function SignalTable({
  signals,
  selectedStock,
  setSelectedStock,
  activePeriod,
  sortBy,
  filterCatalyst,
  excludeSectors,
  unconfirmedCount,
  onShowUnconfirmed,
}) {
  const sectorFiltered = filterBySector(signals, excludeSectors)
  const filtered = filterSignals(sectorFiltered, filterCatalyst)
  const sorted = sortSignals(filtered, sortBy, activePeriod)

  if (signals.length === 0) {
    return (
      <div className="flex items-center justify-center py-20 text-text-muted text-sm">
        <div className="text-center">
          <div className="text-3xl mb-2 opacity-30">&#9473;</div>
          <div>Loading signals...</div>
          <div className="text-xs mt-1">Waiting for API connection</div>
        </div>
      </div>
    )
  }

  if (sorted.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-text-muted text-sm">
        No signals match the current filter.
      </div>
    )
  }

  return (
    <div className="overflow-auto">
      <div className="px-3 py-2 text-xs font-semibold text-text-primary border-b border-border">
        Confirmed Movers <span className="text-text-muted font-normal">({sorted.length})</span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="px-3 py-2 text-xs font-medium text-text-muted w-16">Score</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted w-14 text-center">Conv.</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted">Stock</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right w-20">Price</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right w-20">Move</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted w-24 text-center">Trend</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right w-16">Vol</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted text-right w-20">Cap</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted w-20 text-center">Signal</th>
            <th className="px-3 py-2 text-xs font-medium text-text-muted">Catalyst</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((stock) => {
            const isSelected = selectedStock?.ticker === stock.ticker
            const move = getMove(stock, activePeriod)
            const pills = getSignalPills(stock)
            const score = stock.momentum_score ?? 0
            const showSector = stock.sector && stock.sector !== 'Unknown' && stock.sector !== 'Other'

            return (
              <tr
                key={stock.ticker}
                onClick={() => setSelectedStock(stock)}
                className={`
                  border-b border-border/60 cursor-pointer transition-colors row-hover
                  ${isSelected ? 'row-selected' : ''}
                `}
              >
                {/* Score */}
                <td className="px-3 py-2.5">
                  <div className="flex flex-col items-center gap-1">
                    <span className={`font-mono text-sm ${getScoreColor(score)}`}>{score}</span>
                    <div className="momentum-bar">
                      <div
                        className="momentum-fill"
                        style={{
                          width: `${score}%`,
                          backgroundColor: getScoreFillColor(score),
                        }}
                      />
                    </div>
                  </div>
                </td>

                {/* Conviction */}
                <td className="px-3 py-2.5 text-center">
                  {(() => {
                    const cs = stock.conviction_score ?? null
                    const cg = stock.conviction_grade ?? ''
                    if (cs == null) return <span className="text-text-muted text-xs">--</span>
                    const colorCls = (cg === 'A+' || cg === 'A')
                      ? 'text-rose-accent font-bold'
                      : cg === 'B'
                        ? 'text-text-secondary'
                        : 'text-text-muted'
                    return (
                      <div className="flex flex-col items-center">
                        <span className={`font-mono text-sm ${colorCls}`}>{cs}</span>
                        <span className={`text-[10px] ${colorCls}`}>{cg}</span>
                      </div>
                    )
                  })()}
                </td>

                {/* Stock */}
                <td className="px-3 py-2.5">
                  <div>
                    <span className="font-mono font-semibold text-text-primary text-[13px]">
                      {stock.ticker}
                    </span>
                    <div className="text-xs text-text-muted truncate max-w-[160px]">
                      {stock.company_name || stock.name || ''}
                    </div>
                    {showSector && (
                      <div className="text-[10px] text-text-muted mt-0.5">{stock.sector}</div>
                    )}
                    {pills.length > 0 && (
                      <div className="flex gap-1 mt-0.5">
                        {pills.map(p => (
                          <span key={p} className="signal-pill">{p}</span>
                        ))}
                      </div>
                    )}
                    {stock.macro_trends && stock.macro_trends.length > 0 && (
                      <div className="flex gap-1 mt-0.5">
                        {stock.macro_trends.map(t => (
                          <span key={t} className="trend-pill">{t}</span>
                        ))}
                      </div>
                    )}
                  </div>
                </td>

                {/* Price */}
                <td className="px-3 py-2.5 text-right">
                  <span className="font-mono font-medium text-text-primary">
                    {formatPrice(stock.price ?? stock.close)}
                  </span>
                </td>

                {/* Move */}
                <td className="px-3 py-2.5 text-right">
                  <span className={`font-mono font-bold ${
                    (move ?? 0) >= 0 ? 'text-up-green' : 'text-down-red'
                  }`}>
                    {formatPct(move)}
                  </span>
                </td>

                {/* Trend */}
                <td className="px-3 py-2.5 text-center">
                  <Sparkline
                    data={stock.price_history}
                    color={(move ?? 0) >= 0 ? '#1A8754' : '#C93B3B'}
                    width={72}
                    height={24}
                  />
                </td>

                {/* Vol */}
                <td className="px-3 py-2.5 text-right">
                  <span className={`font-mono font-medium ${
                    (stock.vol_ratio ?? 0) >= 5
                      ? 'text-vol-amber font-bold'
                      : 'text-text-secondary'
                  }`}>
                    {formatVolRatio(stock.vol_ratio)}
                  </span>
                </td>

                {/* Cap */}
                <td className="px-3 py-2.5 text-right">
                  <span className="font-mono text-text-secondary text-xs">
                    {formatMarketCap(stock.market_cap)}
                  </span>
                </td>

                {/* Signal */}
                <td className="px-3 py-2.5 text-center">
                  <span className={getCatalystClass(stock.catalyst_classification)}>
                    {(stock.catalyst_classification || 'NONE').toUpperCase()}
                  </span>
                </td>

                {/* Catalyst */}
                <td className="px-3 py-2.5">
                  <div className="news-line text-xs text-text-primary">
                    {stock.news_headline || stock.catalyst_headline || '—'}
                  </div>
                  {(stock.news_source || stock.news_date) && (
                    <div className="text-[10px] text-text-muted mt-0.5">
                      {stock.news_source}{stock.news_source && stock.news_date ? ' · ' : ''}
                      {stock.news_date ? timeAgo(stock.news_date) : ''}
                    </div>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
      {unconfirmedCount > 0 && onShowUnconfirmed && (
        <div className="px-3 py-3 border-t border-border text-center">
          <button
            onClick={onShowUnconfirmed}
            className="text-xs text-text-muted hover:text-text-secondary transition-colors"
          >
            Show {unconfirmedCount} unconfirmed movers (no news catalyst)
          </button>
        </div>
      )}
    </div>
  )
}
