import React, { useState, useRef, useEffect } from 'react'

const sortOptions = [
  { key: 'score', label: 'Score' },
  { key: 'move', label: '% Move' },
  { key: 'volume', label: 'Volume' },
  { key: 'cap', label: 'Mkt Cap' },
  { key: 'newest', label: 'Newest' },
  { key: 'conviction', label: 'Conviction' },
]

const filterOptions = [
  { key: 'all', label: 'All' },
  { key: 'GREEN', label: 'Green' },
  { key: 'YELLOW', label: 'Yellow' },
  { key: 'RED', label: 'Red' },
]

const SECTOR_OPTIONS = [
  'Basic Materials',
  'Energy',
  'Industrials',
  'Consumer Cyclical',
  'Consumer Defensive',
  'Healthcare',
  'Financial Services',
  'Technology',
  'Communication Services',
  'Real Estate',
  'Utilities',
  'Other',
]

export default function SortFilterBar({
  sortBy, setSortBy,
  filterCatalyst, setFilterCatalyst,
  excludeSectors, setExcludeSectors,
}) {
  const [sectorOpen, setSectorOpen] = useState(false)
  const dropdownRef = useRef(null)

  // Close dropdown on outside click
  useEffect(() => {
    if (!sectorOpen) return
    function handleClick(e) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setSectorOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [sectorOpen])

  const excludedCount = excludeSectors ? excludeSectors.size : 0

  function toggleSector(sector) {
    const next = new Set(excludeSectors)
    if (next.has(sector)) {
      next.delete(sector)
    } else {
      next.add(sector)
    }
    setExcludeSectors(next)
  }

  return (
    <div className="flex items-center justify-between px-4 py-2">
      {/* Sort */}
      <div className="flex items-center gap-1">
        <span className="text-xs text-text-muted mr-1.5">Sort:</span>
        {sortOptions.map((opt) => (
          <button
            key={opt.key}
            onClick={() => setSortBy(opt.key)}
            className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
              sortBy === opt.key
                ? 'bg-rose-light text-rose-accent border border-rose-hover'
                : 'text-text-secondary hover:bg-card-secondary border border-transparent'
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Filter */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1">
          <span className="text-xs text-text-muted mr-1.5">Signal:</span>
          {filterOptions.map((opt) => {
            const isActive = filterCatalyst === opt.key
            let colorClass = ''
            if (isActive) {
              switch (opt.key) {
                case 'GREEN': colorClass = 'bg-up-green-bg text-up-green border-up-green/20'; break
                case 'YELLOW': colorClass = 'bg-vol-amber-bg text-vol-amber border-vol-amber/20'; break
                case 'RED': colorClass = 'bg-down-red-bg text-down-red border-down-red/20'; break
                default: colorClass = 'bg-rose-light text-rose-accent border-rose-hover'
              }
            }
            return (
              <button
                key={opt.key}
                onClick={() => setFilterCatalyst(opt.key)}
                className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
                  isActive
                    ? colorClass
                    : 'text-text-secondary hover:bg-card-secondary border-transparent'
                }`}
              >
                {opt.label}
              </button>
            )
          })}
        </div>

        {/* Sector filter dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            onClick={() => setSectorOpen((v) => !v)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors border ${
              excludedCount > 0
                ? 'bg-rose-light text-rose-accent border-rose-hover'
                : 'text-text-secondary hover:bg-card-secondary border-transparent'
            }`}
          >
            Sectors{excludedCount > 0 ? ` (${SECTOR_OPTIONS.length - excludedCount})` : ''}
          </button>

          {sectorOpen && (
            <div className="absolute right-0 top-full mt-1 z-50 w-48 bg-card border border-border rounded-lg shadow-lg py-1.5">
              {SECTOR_OPTIONS.map((sector) => {
                const checked = !excludeSectors.has(sector)
                return (
                  <label
                    key={sector}
                    className="flex items-center gap-2 px-3 py-1.5 text-xs text-text-primary hover:bg-card-secondary cursor-pointer select-none"
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleSector(sector)}
                      className="rounded border-border text-rose-accent focus:ring-rose-accent accent-rose-500"
                    />
                    {sector}
                  </label>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
