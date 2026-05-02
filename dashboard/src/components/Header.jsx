import React, { useState, useEffect, useRef } from 'react'

function DateSelector({ selectedDate, onDateChange }) {
  const [scans, setScans] = useState([])
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    fetch('./data/scan_history.json')
      .then(res => res.json())
      .then(data => {
        if (data.scans) setScans(data.scans)
      })
      .catch(() => {})
  }, [])

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  function formatDate(dateStr) {
    if (!dateStr) return ''
    const d = new Date(dateStr + 'T12:00:00')
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  const label = selectedDate ? formatDate(selectedDate) : 'Latest'

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(prev => !prev)}
        className="flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium
                   bg-card-secondary border border-border text-text-secondary
                   hover:text-text-primary hover:border-text-muted transition-colors"
      >
        <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
        </svg>
        {label}
        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && scans.length > 0 && (
        <div className="absolute right-0 top-full mt-1 w-64 bg-card border border-border
                        rounded-lg shadow-lg z-50 max-h-64 overflow-y-auto">
          <button
            onClick={() => { onDateChange(null); setOpen(false) }}
            className={`w-full text-left px-3 py-2 text-xs hover:bg-card-secondary transition-colors
                        border-b border-border ${!selectedDate ? 'text-rose-accent font-semibold' : 'text-text-secondary'}`}
          >
            Latest scan
          </button>
          {scans.map(scan => (
            <button
              key={scan.date}
              onClick={() => { onDateChange(scan.date); setOpen(false) }}
              className={`w-full text-left px-3 py-2 text-xs hover:bg-card-secondary transition-colors
                          border-b border-border last:border-b-0
                          ${selectedDate === scan.date ? 'text-rose-accent font-semibold' : 'text-text-secondary'}`}
            >
              <div className="flex justify-between items-center">
                <span>{formatDate(scan.date)}</span>
                <span className="text-text-muted">
                  {scan.signals} signals / {scan.confirmed} confirmed
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Header({ activeView, setActiveView, lastScan, selectedDate, onDateChange }) {
  const exchanges = ['TSX', 'TSXV', 'CSE', 'NEO']

  function formatViewingDate(dateStr) {
    const d = new Date(dateStr + 'T12:00:00')
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  }

  return (
    <header className="bg-card border-b border-border px-6 py-3">
      <div className="flex items-center justify-between">
        {/* Left: Logo + Title + Exchanges */}
        <div className="flex items-center gap-4">
          <div className="w-9 h-9 rounded-lg bg-rose-accent flex items-center justify-center">
            <span className="text-white font-bold text-lg font-mono">M</span>
          </div>
          <div>
            <h1 className="text-lg font-semibold text-text-primary leading-tight">Momentum Scanner</h1>
            <div className="flex items-center gap-1.5 mt-0.5">
              {exchanges.map((ex, i) => (
                <React.Fragment key={ex}>
                  <span className="text-[11px] font-medium text-text-muted tracking-wide">{ex}</span>
                  {i < exchanges.length - 1 && <span className="text-text-muted/40 text-[10px]">&middot;</span>}
                </React.Fragment>
              ))}
            </div>
          </div>
        </div>

        {/* Center: Auto-scan status + Date selector */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-up-green opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-up-green"></span>
            </span>
            <span>Auto-scanned daily at close</span>
            {lastScan && !selectedDate && (
              <span className="text-text-muted text-xs ml-1">Last: {lastScan}</span>
            )}
          </div>
          {selectedDate && (
            <span className="text-xs font-medium text-amber-400 bg-amber-400/10 px-2 py-0.5 rounded">
              Viewing: {formatViewingDate(selectedDate)}
            </span>
          )}
          <DateSelector selectedDate={selectedDate} onDateChange={onDateChange} />
        </div>

        {/* Right: View toggle */}
        <div className="flex items-center gap-1 bg-card-secondary rounded-lg p-1 border border-border">
          <button
            onClick={() => setActiveView('movers')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeView === 'movers'
                ? 'bg-rose-accent text-white'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Movers
          </button>
          <button
            onClick={() => setActiveView('watchlist')}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-colors ${
              activeView === 'watchlist'
                ? 'bg-rose-accent text-white'
                : 'text-text-secondary hover:text-text-primary'
            }`}
          >
            Watchlist
          </button>
        </div>
      </div>
    </header>
  )
}
