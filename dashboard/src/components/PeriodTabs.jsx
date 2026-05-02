import React from 'react'

const tabs = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This Week' },
  { key: 'month', label: '30 Days' },
]

export default function PeriodTabs({ activePeriod, setActivePeriod, signalCounts }) {
  return (
    <div className="flex items-center gap-1 border-b border-border">
      {tabs.map((tab) => (
        <button
          key={tab.key}
          onClick={() => setActivePeriod(tab.key)}
          className={`relative px-5 py-2.5 text-sm font-medium transition-colors ${
            activePeriod === tab.key
              ? 'text-rose-accent'
              : 'text-text-secondary hover:text-text-primary'
          }`}
        >
          <span className="flex items-center gap-2">
            {tab.label}
            {signalCounts?.[tab.key] != null && (
              <span className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded-full ${
                activePeriod === tab.key
                  ? 'bg-rose-light text-rose-accent'
                  : 'bg-card-secondary text-text-muted'
              }`}>
                {signalCounts[tab.key]}
              </span>
            )}
          </span>
          {activePeriod === tab.key && (
            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-rose-accent rounded-t-full" />
          )}
        </button>
      ))}
    </div>
  )
}
