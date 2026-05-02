import React, { useState } from 'react'
import Sparkline from './Sparkline.jsx'
import {
  formatPrice,
  formatPct,
  formatMarketCap,
  formatVolRatio,
  getCatalystClass,
  timeAgo,
} from '../lib/format.js'

const checklistItems = [
  'Verify news source & claims',
  'Check insider trading (SEDI)',
  'Review financials / burn rate',
  'Check share structure & dilution',
  'Confirm volume is organic',
  'Review management track record',
  'Set stop-loss level',
]

export default function DetailPanel({ stock, onAddWatchlist }) {
  const [checklist, setChecklist] = useState(Array(checklistItems.length).fill(false))
  const [tradeType, setTradeType] = useState('A')
  const [notes, setNotes] = useState('')
  const [lastTicker, setLastTicker] = useState(null)

  // Reset checklist and notes when selecting a different stock
  if (stock && stock.ticker !== lastTicker) {
    setChecklist(Array(checklistItems.length).fill(false))
    setNotes('')
    setLastTicker(stock.ticker)
  }

  if (!stock) {
    return (
      <div className="w-[440px] min-w-[440px] border-l border-border bg-card-secondary flex items-center justify-center">
        <div className="text-center text-text-muted text-sm px-8">
          <div className="text-4xl mb-3 opacity-20">&#8594;</div>
          <div>Select a stock from the list</div>
          <div className="text-xs mt-1">to view detailed analysis</div>
        </div>
      </div>
    )
  }

  const toggleCheck = (i) => {
    const next = [...checklist]
    next[i] = !next[i]
    setChecklist(next)
  }

  const handleAddWatchlist = async () => {
    try {
      await fetch('/api/watchlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: stock.ticker,
          entry_price: stock.price ?? stock.close,
          trade_type: tradeType,
          notes,
        }),
      })
      onAddWatchlist?.()
    } catch (err) {
      console.error('Failed to add to watchlist:', err)
    }
  }

  const score = stock.momentum_score ?? 0
  const pills = []
  if ((stock.pct_move_10d ?? 0) >= 0.30) pills.push('Breakout')
  if ((stock.vol_ratio ?? 0) >= 5) pills.push('Vol Surge')
  if (stock.near_52w_high) pills.push('New High')

  // Build volume bars data
  const volBars = stock.volume_history || Array.from({ length: 10 }, (_, i) => ({
    vol: Math.random() * 1000000 + 200000,
    surge: i >= 7,
  }))

  return (
    <div className="w-[440px] min-w-[440px] border-l border-border bg-card overflow-y-auto max-h-[calc(100vh-120px)]">
      {/* Header */}
      <div className="px-5 py-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="font-mono text-xl font-bold text-text-primary">{stock.ticker}</span>
            <span className={getCatalystClass(stock.catalyst_classification)}>
              {(stock.catalyst_classification || 'NONE').toUpperCase()}
            </span>
          </div>
          <button
            onClick={handleAddWatchlist}
            className="px-3 py-1.5 rounded-lg bg-rose-accent text-white text-xs font-semibold hover:bg-rose-accent/90 transition-colors"
          >
            + Watchlist
          </button>
        </div>
        <div className="text-xs text-text-secondary mt-1">
          {stock.company_name || stock.name || ''}{' '}
          {stock.exchange && <span className="text-text-muted">· {stock.exchange}</span>}{' '}
          {stock.sector && <span className="text-text-muted">· {stock.sector}</span>}
        </div>
        {pills.length > 0 && (
          <div className="flex gap-1.5 mt-2">
            {pills.map(p => <span key={p} className="signal-pill">{p}</span>)}
          </div>
        )}
        {stock.macro_trends && stock.macro_trends.length > 0 && (
          <div className="flex gap-1.5 mt-1.5">
            {stock.macro_trends.map(t => <span key={t} className="trend-pill">{t}</span>)}
          </div>
        )}
      </div>

      {/* Price Surge */}
      <div className="px-5 py-4 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Price Surge</h3>
        <div className="grid grid-cols-2 gap-2 mb-3">
          <StatCard label="Price" value={formatPrice(stock.price ?? stock.close)} />
          <StatCard
            label="10d Move"
            value={formatPct(stock.pct_move_10d)}
            bg="bg-up-green-bg"
            valueColor="text-up-green"
          />
          <StatCard label="30d Move" value={formatPct(stock.pct_move_30d)} />
          <StatCard label="Mkt Cap" value={formatMarketCap(stock.market_cap)} />
        </div>
        <div className="bg-card-secondary rounded-lg p-3">
          <Sparkline
            data={stock.price_history}
            color={((stock.pct_move_10d ?? 0) >= 0) ? '#1A8754' : '#C93B3B'}
            width={380}
            height={60}
          />
        </div>
      </div>

      {/* Conviction Breakdown */}
      {stock.conviction_score != null && (
        <div className="px-5 py-4 border-b border-border">
          <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Conviction Breakdown</h3>
          <div className="flex items-center gap-3 mb-3">
            <span className={`font-mono text-2xl font-bold ${
              (stock.conviction_grade === 'A+' || stock.conviction_grade === 'A')
                ? 'text-rose-accent'
                : stock.conviction_grade === 'B'
                  ? 'text-text-secondary'
                  : 'text-text-muted'
            }`}>
              {stock.conviction_score}
            </span>
            <span className={`text-lg font-semibold ${
              (stock.conviction_grade === 'A+' || stock.conviction_grade === 'A')
                ? 'text-rose-accent'
                : stock.conviction_grade === 'B'
                  ? 'text-text-secondary'
                  : 'text-text-muted'
            }`}>
              {stock.conviction_grade}
            </span>
          </div>
          <div className="space-y-2">
            {[
              { label: 'Signal Strength', weight: '25%', key: 'signal_strength' },
              { label: 'Catalyst Quality', weight: '35%', key: 'catalyst_quality' },
              { label: 'Setup Quality', weight: '20%', key: 'setup_quality' },
              { label: 'Pattern Match', weight: '20%', key: 'pattern_match' },
            ].map(({ label, weight, key }) => {
              const val = stock.conviction_sub_scores?.[key] ?? 0
              return (
                <div key={key}>
                  <div className="flex justify-between text-[11px] mb-0.5">
                    <span className="text-text-secondary">{label} <span className="text-text-muted">({weight})</span></span>
                    <span className="font-mono text-text-primary">{val}%</span>
                  </div>
                  <div className="w-full h-2 rounded-full bg-card-secondary overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${val}%`, backgroundColor: '#C25A62' }}
                    />
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Volume Signal */}
      <div className="px-5 py-4 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Volume Signal</h3>
        <div className="grid grid-cols-2 gap-2 mb-3">
          <StatCard
            label="Vol Ratio"
            value={formatVolRatio(stock.vol_ratio)}
            bg={(stock.vol_ratio ?? 0) >= 5 ? 'bg-vol-amber-bg' : undefined}
            valueColor={(stock.vol_ratio ?? 0) >= 5 ? 'text-vol-amber' : undefined}
          />
          <StatCard
            label="Avg Vol"
            value={stock.avg_volume ? `${(stock.avg_volume / 1000).toFixed(0)}K` : '—'}
          />
        </div>
        <div className="bg-card-secondary rounded-lg p-3">
          <VolumeBars data={volBars} />
        </div>
      </div>

      {/* Catalyst & News */}
      <div className="px-5 py-4 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Catalyst & News</h3>
        {stock.news_items && stock.news_items.length > 0 ? (
          stock.news_items.map((item, i) => (
            <NewsItem key={i} item={item} isPrimary={i === 0} classification={stock.catalyst_classification} />
          ))
        ) : stock.news_headline || stock.catalyst_headline ? (
          <NewsItem
            item={{
              title: stock.news_headline || stock.catalyst_headline,
              summary: stock.catalyst_summary || '',
              source: stock.news_source,
              date: stock.news_date,
              tags: stock.commitment_tags,
            }}
            isPrimary
            classification={stock.catalyst_classification}
          />
        ) : (
          <div className="text-xs text-text-muted py-2">No catalyst news found</div>
        )}
      </div>

      {/* Diligence Checklist */}
      <div className="px-5 py-4 border-b border-border">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Diligence Checklist</h3>
        <div className="space-y-1.5">
          {checklistItems.map((item, i) => (
            <label
              key={i}
              className="flex items-center gap-2.5 cursor-pointer text-sm text-text-secondary hover:text-text-primary"
            >
              <input
                type="checkbox"
                checked={checklist[i]}
                onChange={() => toggleCheck(i)}
                className="w-4 h-4 rounded border-border accent-rose-accent"
              />
              {item}
            </label>
          ))}
        </div>
      </div>

      {/* Trade Type & Notes */}
      <div className="px-5 py-4">
        <h3 className="text-xs font-semibold text-text-muted uppercase tracking-wider mb-3">Trade Setup</h3>
        <div className="flex items-center gap-3 mb-3">
          <span className="text-xs text-text-secondary">Type:</span>
          {['A', 'B'].map(t => (
            <button
              key={t}
              onClick={() => setTradeType(t)}
              className={`w-8 h-8 rounded-lg text-sm font-bold transition-colors ${
                tradeType === t
                  ? 'bg-rose-accent text-white'
                  : 'bg-card-secondary text-text-secondary border border-border hover:border-rose-accent/30'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Trade notes..."
          rows={3}
          className="w-full rounded-lg border border-border bg-card-secondary px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-rose-accent/40 resize-none"
        />
      </div>
    </div>
  )
}

function StatCard({ label, value, bg, valueColor }) {
  return (
    <div className={`rounded-lg px-3 py-2.5 ${bg || 'bg-card-secondary'}`}>
      <div className="text-[10px] font-medium text-text-muted uppercase tracking-wider">{label}</div>
      <div className={`font-mono font-semibold text-base mt-0.5 ${valueColor || 'text-text-primary'}`}>
        {value}
      </div>
    </div>
  )
}

function NewsItem({ item, isPrimary, classification }) {
  const bgMap = {
    GREEN: 'bg-up-green-bg border-up-green/15',
    YELLOW: 'bg-vol-amber-bg border-vol-amber/15',
    RED: 'bg-down-red-bg border-down-red/15',
  }
  const bgClass = isPrimary && classification
    ? bgMap[classification.toUpperCase()] || 'bg-card-secondary border-border'
    : 'bg-card-secondary border-border'

  return (
    <div className={`rounded-lg border p-3 mb-2 ${bgClass}`}>
      <div className="text-xs font-semibold text-text-primary leading-snug">{item.title}</div>
      {item.summary && (
        <div className="text-[11px] text-text-secondary mt-1 leading-relaxed">{item.summary}</div>
      )}
      <div className="flex items-center gap-2 mt-1.5">
        {item.source && <span className="text-[10px] text-text-muted">{item.source}</span>}
        {item.date && <span className="text-[10px] text-text-muted">{timeAgo(item.date)}</span>}
        {item.tags && item.tags.length > 0 && item.tags.map((tag, i) => (
          <span key={i} className="text-[9px] bg-card px-1.5 py-0.5 rounded text-text-muted font-medium">
            {tag}
          </span>
        ))}
      </div>
    </div>
  )
}

function VolumeBars({ data }) {
  if (!data || data.length === 0) return null

  const maxVol = Math.max(...data.map(d => typeof d === 'object' ? d.vol : d))

  return (
    <svg width="100%" height="48" viewBox="0 0 380 48" preserveAspectRatio="none">
      {data.map((d, i) => {
        const vol = typeof d === 'object' ? d.vol : d
        const isSurge = typeof d === 'object' ? d.surge : false
        const barWidth = 380 / data.length - 3
        const barHeight = (vol / maxVol) * 44
        const x = i * (380 / data.length) + 1.5
        const y = 48 - barHeight

        return (
          <rect
            key={i}
            x={x}
            y={y}
            width={barWidth}
            height={barHeight}
            rx="2"
            fill={isSurge ? '#B87B2B' : '#E5E2DC'}
          />
        )
      })}
    </svg>
  )
}
