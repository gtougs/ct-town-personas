import React, { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer, Legend } from 'recharts'
import { Card, SectionLabel, TrendBadge, Skel } from './ui.jsx'
import { useFetch } from '../hooks/useFetch.js'
import { api } from '../api.js'

const INDICATORS = [
  // Enriched (real time series)
  { key: 'zillow_home_value',          label: 'Home Value (Zillow)',       fmt: v => `$${v?.toLocaleString()}`,  tag: 'live' },
  { key: 'annual_business_formations', label: 'Business Formations',       fmt: v => v?.toLocaleString(),         tag: 'live' },
  // ACS snapshots
  { key: 'median_household_income',    label: 'Household Income (ACS)',    fmt: v => `$${v?.toLocaleString()}`,  tag: 'acs' },
  { key: 'median_home_value',          label: 'Home Value (ACS)',          fmt: v => `$${v?.toLocaleString()}`,  tag: 'acs' },
  { key: 'median_rent',                label: 'Median Rent',               fmt: v => `$${v?.toLocaleString()}`,  tag: 'acs' },
  { key: 'gini_ratio',                 label: 'Gini Ratio',                fmt: v => v?.toFixed(3),              tag: 'acs' },
  { key: 'snap_recipients',            label: 'SNAP Recipients %',         fmt: v => `${v?.toFixed(1)}%`,        tag: 'acs' },
  { key: 'single_parent_families',     label: 'Single Parent Families %',  fmt: v => `${v?.toFixed(1)}%`,        tag: 'acs' },
  { key: 'housing_permits',            label: 'Housing Permits',           fmt: v => v?.toLocaleString(),         tag: 'acs' },
]

export default function ForecastPanel({ town }) {
  const [active, setActive] = useState('zillow_home_value')
  const selected = INDICATORS.find(i => i.key === active) || INDICATORS[0]

  const { data, loading, error } = useFetch(
    town ? () => api.forecast(town, active) : null,
    [town, active]
  )

  if (!town) return null

  const needsMoreData = error && error.includes('Not enough data')
  const chartData = data ? [
    ...data.historical.map(p => ({ year: p.year, historical: p.value })),
    ...data.forecast.map(p => ({ year: p.year, forecast: p.value, lower: p.lower, upper: p.upper })),
  ] : []
  const splitYear = data?.historical?.at(-1)?.year

  return (
    <Card>
      <SectionLabel>Trend forecast</SectionLabel>

      {/* Indicator selector with live/acs tags */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 20 }}>
        {INDICATORS.map(ind => (
          <button key={ind.key} onClick={() => setActive(ind.key)} style={{
            padding: '5px 11px', fontSize: 11, fontFamily: 'var(--mono)',
            background: active === ind.key ? 'var(--accent)' : 'var(--paper-2)',
            color: active === ind.key ? '#fff' : 'var(--ink-3)',
            border: `0.5px solid ${active === ind.key ? 'transparent' : ind.tag === 'live' ? 'var(--teal)' : 'var(--paper-3)'}`,
            borderRadius: 20, cursor: 'pointer', transition: 'all 0.15s',
            display: 'flex', alignItems: 'center', gap: 5,
          }}>
            {ind.tag === 'live' && (
              <span style={{
                width: 6, height: 6, borderRadius: '50%',
                background: active === ind.key ? '#fff' : 'var(--teal)',
                flexShrink: 0,
              }} />
            )}
            {ind.label}
          </button>
        ))}
      </div>

      {/* Data source note */}
      <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginBottom: 14 }}>
        {selected.tag === 'live'
          ? '● Live data source — real annual time series through 2024'
          : '○ ACS snapshot — limited vintages, fewer data points'}
      </div>

      {loading && <Skel h={220} />}

      {needsMoreData && (
        <div style={{
          padding: '24px 20px', textAlign: 'center',
          background: 'var(--paper-2)', borderRadius: 'var(--r)',
          border: '0.5px solid var(--paper-3)',
        }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>📊</div>
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)', marginBottom: 6 }}>
            Not enough data points for this town
          </p>
          <p style={{ fontSize: 12, color: 'var(--ink-3)', maxWidth: 380, margin: '0 auto' }}>
            Try a larger town, or switch to a live data source (green dot indicators above).
          </p>
        </div>
      )}

      {error && !needsMoreData && (
        <p style={{ fontSize: 12, color: 'var(--coral)' }}>Failed to load: {error}</p>
      )}

      {data && !loading && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontFamily: 'var(--serif)' }}>{selected.label} — {town}</span>
            <TrendBadge direction={data.trend_direction} magnitude={data.trend_magnitude} />
          </div>

          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--paper-3)" />
              <XAxis
                dataKey="year"
                tick={{ fontSize: 11, fontFamily: 'var(--mono)', fill: 'var(--ink-3)' }}
              />
              <YAxis
                tickFormatter={v => {
                  const s = selected.fmt(v)
                  return s.replace(/,\d{3}$/, 'k').replace(/\$(\d+)k/, '$$$1k')
                }}
                tick={{ fontSize: 11, fontFamily: 'var(--mono)', fill: 'var(--ink-3)' }}
                width={60}
              />
              <Tooltip
                formatter={(v, name) => [selected.fmt(v), name === 'historical' ? 'Historical' : 'Forecast']}
                labelStyle={{ fontFamily: 'var(--mono)', fontSize: 11 }}
                contentStyle={{
                  background: 'var(--paper)', border: '0.5px solid var(--paper-3)',
                  borderRadius: 'var(--r)', fontSize: 12,
                }}
              />
              <Legend
                formatter={v => v === 'historical' ? 'Historical' : 'Forecast (Prophet)'}
                wrapperStyle={{ fontSize: 11, fontFamily: 'var(--mono)', paddingTop: 8 }}
              />
              {splitYear && (
                <ReferenceLine
                  x={splitYear}
                  stroke="var(--ink-3)"
                  strokeDasharray="4 4"
                  label={{ value: '← actual  forecast →', position: 'top', fontSize: 9, fontFamily: 'var(--mono)', fill: 'var(--ink-3)' }}
                />
              )}
              <Line
                dataKey="historical"
                stroke="var(--accent)"
                strokeWidth={2.5}
                dot={{ r: 4, fill: 'var(--accent)', strokeWidth: 0 }}
                activeDot={{ r: 6 }}
                connectNulls
              />
              <Line
                dataKey="forecast"
                stroke="var(--accent-2)"
                strokeWidth={1.5}
                strokeDasharray="6 3"
                dot={{ r: 3, fill: 'var(--accent-2)', strokeWidth: 0 }}
                connectNulls
              />
            </LineChart>
          </ResponsiveContainer>

          <p style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 8, fontFamily: 'var(--mono)' }}>
            {data.historical.length} historical data points · {data.forecast.length}-year Prophet forecast
            {data.forecast[0]?.upper ? ' · 80% confidence interval' : ''}
          </p>
        </>
      )}
    </Card>
  )
}
