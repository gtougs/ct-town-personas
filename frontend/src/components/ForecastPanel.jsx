import React, { useState } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
import { Card, SectionLabel, TrendBadge, Skel } from './ui.jsx'
import { useFetch } from '../hooks/useFetch.js'
import { api } from '../api.js'

const INDICATORS = [
  { key: 'median_household_income', label: 'Median household income',  fmt: v => `$${v?.toLocaleString()}` },
  { key: 'median_home_value',       label: 'Median home value',         fmt: v => `$${v?.toLocaleString()}` },
  { key: 'median_rent',             label: 'Median rent',               fmt: v => `$${v?.toLocaleString()}` },
  { key: 'business_formations',     label: 'Business formations',       fmt: v => v?.toLocaleString() },
  { key: 'gini_ratio',              label: 'Gini ratio (inequality)',    fmt: v => v?.toFixed(3) },
  { key: 'snap_recipients',         label: 'SNAP recipients %',         fmt: v => `${v?.toFixed(1)}%` },
]

export default function ForecastPanel({ town }) {
  const [active, setActive] = useState('median_household_income')
  const selected = INDICATORS.find(i => i.key === active) || INDICATORS[0]

  const { data, loading, error } = useFetch(
    town ? () => api.forecast(town, active) : null,
    [town, active]
  )

  if (!town) return null

  const needsMoreData = error && error.includes('Not enough data')
  const chartData = data ? [
    ...data.historical.map(p => ({ year: p.year, value: p.value, type: 'historical' })),
    ...data.forecast.map(p => ({ year: p.year, value: p.value, lower: p.lower, upper: p.upper, type: 'forecast' })),
  ] : []
  const splitYear = data?.historical?.at(-1)?.year

  return (
    <Card>
      <SectionLabel>Trend forecast</SectionLabel>

      {/* Indicator selector */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 20 }}>
        {INDICATORS.map(ind => (
          <button key={ind.key} onClick={() => setActive(ind.key)} style={{
            padding: '5px 11px', fontSize: 11, fontFamily: 'var(--mono)',
            background: active === ind.key ? 'var(--accent)' : 'var(--paper-2)',
            color: active === ind.key ? '#fff' : 'var(--ink-3)',
            border: `0.5px solid ${active === ind.key ? 'transparent' : 'var(--paper-3)'}`,
            borderRadius: 20, cursor: 'pointer', transition: 'all 0.15s',
          }}>
            {ind.label}
          </button>
        ))}
      </div>

      {loading && <Skel h={200} />}

      {needsMoreData && (
        <div style={{
          padding: '24px 20px', textAlign: 'center',
          background: 'var(--paper-2)', borderRadius: 'var(--r)',
          border: '0.5px solid var(--paper-3)',
        }}>
          <div style={{ fontSize: 24, marginBottom: 8 }}>📊</div>
          <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)', marginBottom: 6 }}>
            Forecasting requires multiple years of data
          </p>
          <p style={{ fontSize: 12, color: 'var(--ink-3)', maxWidth: 380, margin: '0 auto' }}>
            Run the pipeline for additional ACS vintages (2018–2021) to enable
            trend charts and 5-year forecasts. Currently only 2022 data is loaded.
          </p>
          <code style={{
            display: 'inline-block', marginTop: 12,
            fontSize: 11, fontFamily: 'var(--mono)',
            background: 'var(--paper-3)', padding: '4px 10px', borderRadius: 4,
          }}>
            make pipeline YEAR=2019 &amp;&amp; make pipeline YEAR=2020 &amp;&amp; make pipeline YEAR=2021
          </code>
        </div>
      )}

      {error && !needsMoreData && (
        <p style={{ fontSize: 12, color: 'var(--coral)' }}>Failed to load forecast: {error}</p>
      )}

      {data && !loading && (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
            <span style={{ fontSize: 13, fontFamily: 'var(--serif)' }}>{selected.label} — {town}</span>
            <TrendBadge direction={data.trend_direction} magnitude={data.trend_magnitude} />
          </div>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 4, right: 8, bottom: 4, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--paper-3)" />
              <XAxis dataKey="year" tick={{ fontSize: 11, fontFamily: 'var(--mono)', fill: 'var(--ink-3)' }} />
              <YAxis
                tickFormatter={v => selected.fmt(v).replace(/\$|%/g, '')}
                tick={{ fontSize: 11, fontFamily: 'var(--mono)', fill: 'var(--ink-3)' }}
                width={52}
              />
              <Tooltip
                formatter={v => [selected.fmt(v), selected.label]}
                labelStyle={{ fontFamily: 'var(--mono)', fontSize: 11 }}
                contentStyle={{ background: 'var(--paper)', border: '0.5px solid var(--paper-3)', borderRadius: 'var(--r)', fontSize: 12 }}
              />
              {splitYear && (
                <ReferenceLine x={splitYear} stroke="var(--ink-3)" strokeDasharray="4 4" label={{
                  value: 'forecast →', position: 'insideTopRight',
                  fontSize: 10, fontFamily: 'var(--mono)', fill: 'var(--ink-3)',
                }} />
              )}
              <Line data={chartData.filter(d => d.type === 'historical')} dataKey="value"
                stroke="var(--accent)" strokeWidth={2}
                dot={{ r: 3, fill: 'var(--accent)', strokeWidth: 0 }} connectNulls />
              <Line data={chartData.filter(d => d.type === 'forecast')} dataKey="value"
                stroke="var(--accent-2)" strokeWidth={1.5} strokeDasharray="5 3"
                dot={{ r: 3, fill: 'var(--accent-2)', strokeWidth: 0 }} connectNulls />
            </LineChart>
          </ResponsiveContainer>
          <p style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 8, fontFamily: 'var(--mono)' }}>
            Dashed = Prophet forecast · Solid = historical ACS data · 80% confidence interval
          </p>
        </>
      )}
    </Card>
  )
}
