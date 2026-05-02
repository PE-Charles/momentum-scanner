import React from 'react'

export default function Sparkline({ data, color = '#1A8754', width = 80, height = 28 }) {
  if (!data || data.length < 2) {
    // Placeholder upward slope
    const placeholderData = [10, 12, 11, 14, 13, 16, 18, 17, 20, 22]
    return <Sparkline data={placeholderData} color={color} width={width} height={height} />
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1
  const padding = 2

  const points = data.map((val, i) => {
    const x = padding + (i / (data.length - 1)) * (width - padding * 2)
    const y = padding + (1 - (val - min) / range) * (height - padding * 2)
    return `${x},${y}`
  }).join(' ')

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className="inline-block">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
