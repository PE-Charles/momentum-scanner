/**
 * Normalize raw scanner signal data for frontend consumption.
 * Ported from api.py _normalize_signal().
 */

/**
 * Normalize a single signal object in place.
 * - Converts pct_move_* and primary_move from raw percentages to decimals
 * - Sets near_52w_high boolean
 * - Flattens news[] into news_headline, news_source, news_date
 * - Builds news_items[] with classification tags for the detail panel
 * - Passes through conviction_score, conviction_grade, conviction_sub_scores
 *
 * @param {Object} s - signal object (mutated in place)
 * @returns {Object} the same object
 */
export function normalizeSignal(s) {
  // Convert percentage numbers to decimals (e.g. 3.15 -> 0.0315, 45.2 -> 0.452)
  const pctKeys = ['pct_move_1d', 'pct_move_5d', 'pct_move_10d', 'pct_move_30d', 'primary_move']
  for (const key of pctKeys) {
    const val = s[key]
    if (val != null) {
      s[key] = val / 100.0
    }
  }

  // 52-week high proximity -> bool
  s.near_52w_high = (s.high_52w_proximity || 0) >= 85

  // Flatten news array into headline/source/date
  const news = s.news || []
  const catalysts = s.catalysts || []

  if (news.length > 0) {
    const first = news[0]
    s.news_headline = first.title || ''
    s.news_source = first.source || ''
    s.news_date = first.published || ''
  } else if (catalysts.length > 0) {
    const first = catalysts[0]
    s.news_headline = first.title || ''
    s.news_source = ''
    s.news_date = ''
  } else {
    s.news_headline = ''
    s.news_source = ''
    s.news_date = ''
  }

  // Build news_items for detail panel
  const items = []
  for (const n of news) {
    const item = {
      title: n.title || '',
      summary: n.summary || '',
      source: n.source || '',
      date: n.published || '',
    }
    // Find matching catalyst classification
    for (const c of catalysts) {
      if (c.title === n.title) {
        const cls = c.classification || {}
        item.classification = cls.classification || ''
        item.tags = []
        if (cls.third_party_committed) {
          item.tags.push('Third party committed')
        }
        if (cls.capital_committed) {
          item.tags.push('Capital committed')
        }
        if (cls.capital_amount_cad) {
          item.tags.push(String(cls.capital_amount_cad))
        }
        break
      }
    }
    items.push(item)
  }
  s.news_items = items

  // conviction_score, conviction_grade, conviction_sub_scores are passed through as-is

  return s
}

/**
 * Normalize an array of signal objects.
 * @param {Object[]} signals
 * @returns {Object[]}
 */
export function normalizeSignals(signals) {
  return signals.map(normalizeSignal)
}
