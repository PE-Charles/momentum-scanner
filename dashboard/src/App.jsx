import React, { useState, useEffect, useCallback, useMemo } from 'react'
import Header from './components/Header.jsx'
import MarketStrip from './components/MarketStrip.jsx'
import PeriodTabs from './components/PeriodTabs.jsx'
import SortFilterBar from './components/SortFilterBar.jsx'
import SignalTable from './components/SignalTable.jsx'
import WatchlistTable from './components/WatchlistTable.jsx'
import DetailPanel from './components/DetailPanel.jsx'
import { normalizeSignals } from './lib/normalize.js'

export default function App() {
  const [signals, setSignals] = useState([])
  const [watchlist, setWatchlist] = useState([])
  const [selectedStock, setSelectedStock] = useState(null)
  const [activeView, setActiveView] = useState('movers')
  const [activePeriod, setActivePeriod] = useState('today')
  const [sortBy, setSortBy] = useState('score')
  const [filterCatalyst, setFilterCatalyst] = useState('all')
  const [excludeSectors, setExcludeSectors] = useState(new Set())
  const [lastScan, setLastScan] = useState(null)
  const [totalScanned, setTotalScanned] = useState(null)
  const [selectedDate, setSelectedDate] = useState(null)

  const fetchSignals = useCallback(async () => {
    try {
      const url = selectedDate
        ? `./data/signals_${selectedDate}.json`
        : './data/signals_latest.json'
      const res = await fetch(url)
      if (res.ok) {
        const raw = await res.json()
        const items = normalizeSignals(Array.isArray(raw) ? raw : [])
        setSignals(items)
        setLastScan(items[0]?.scan_time ?? null)
        setTotalScanned(items.length)
      }
    } catch (err) {
      console.warn('Could not fetch signals:', err.message)
    }
  }, [selectedDate])

  useEffect(() => {
    fetchSignals()
  }, [fetchSignals])

  const handleDateChange = useCallback((date) => {
    setSelectedDate(date)
  }, [])

  const confirmedSignals = useMemo(
    () => signals.filter(s => s.news_headline || s.catalyst_headline),
    [signals]
  )
  const unconfirmedSignals = useMemo(
    () => signals.filter(s => !s.news_headline && !s.catalyst_headline),
    [signals]
  )

  const [showUnconfirmed, setShowUnconfirmed] = useState(false)

  const signalCounts = useMemo(() => ({
    today: confirmedSignals.filter(s => (s.pct_move_1d ?? 0) >= 0.05).length,
    week: confirmedSignals.filter(s => (s.pct_move_5d ?? 0) >= 0.10).length,
    month: confirmedSignals.filter(s => (s.pct_move_10d ?? 0) >= 0.20).length,
  }), [confirmedSignals])

  return (
    <div className="min-h-screen bg-warm-bg">
      <Header
        activeView={activeView}
        setActiveView={setActiveView}
        lastScan={lastScan}
        selectedDate={selectedDate}
        onDateChange={handleDateChange}
      />
      <MarketStrip
        signalCount={signals.length}
        stockCount={totalScanned}
        confirmedCount={confirmedSignals.length}
      />

      <div className="flex flex-1">
        {/* Main List */}
        <div className="flex-1 min-w-0">
          {activeView === 'movers' ? (
            <>
              <div className="bg-card border-b border-border px-4">
                <PeriodTabs
                  activePeriod={activePeriod}
                  setActivePeriod={setActivePeriod}
                  signalCounts={signalCounts}
                />
              </div>
              <div className="bg-card border-b border-border">
                <SortFilterBar
                  sortBy={sortBy}
                  setSortBy={setSortBy}
                  filterCatalyst={filterCatalyst}
                  setFilterCatalyst={setFilterCatalyst}
                  excludeSectors={excludeSectors}
                  setExcludeSectors={setExcludeSectors}
                />
              </div>
              <div className="bg-card">
                <SignalTable
                  signals={confirmedSignals}
                  selectedStock={selectedStock}
                  setSelectedStock={setSelectedStock}
                  activePeriod={activePeriod}
                  sortBy={sortBy}
                  filterCatalyst={filterCatalyst}
                  excludeSectors={excludeSectors}
                  unconfirmedCount={unconfirmedSignals.length}
                  onShowUnconfirmed={() => setShowUnconfirmed(prev => !prev)}
                />
              </div>
              {showUnconfirmed && (
                <div className="bg-card mt-1">
                  <div className="px-3 py-2 text-xs font-semibold text-text-muted border-b border-border">
                    Unconfirmed Movers <span className="font-normal">({unconfirmedSignals.length})</span>
                  </div>
                  <SignalTable
                    signals={unconfirmedSignals}
                    selectedStock={selectedStock}
                    setSelectedStock={setSelectedStock}
                    activePeriod={activePeriod}
                    sortBy={sortBy}
                    filterCatalyst={filterCatalyst}
                    excludeSectors={excludeSectors}
                  />
                </div>
              )}
            </>
          ) : (
            <div className="bg-card">
              <div className="px-5 py-3 border-b border-border">
                <h2 className="text-sm font-semibold text-text-primary">Watchlist</h2>
              </div>
              <WatchlistTable watchlist={watchlist} />
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <DetailPanel
          stock={selectedStock}
          onAddWatchlist={() => {}}
        />
      </div>
    </div>
  )
}
