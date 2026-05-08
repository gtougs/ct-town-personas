import React from 'react'
import { Card, Stat, SignalBadge, SectionLabel, Skel, WeightBar } from './ui.jsx'

const ARCHETYPE_COLORS = {
  'Affluent Suburban':        '#1a3a5c',
  'Working-Class Urban':      '#6b3a2a',
  'Rural / Small Town':       '#2a4a2a',
  'Young Professional':       '#2d3a6b',
  'Mixed-Income Transitional':'#5a3a6b',
}

export default function BusinessView({ data, loading }) {
  if (loading) return <BizSkeleton />
  if (!data) return null

  const personas = data.personas || []

  return (
    <div className="fade-up" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Market composition */}
      <Card>
        <SectionLabel>Market composition by archetype</SectionLabel>
        {personas.map(p => (
          <WeightBar
            key={p.archetype}
            label={p.archetype}
            weight={p.weight}
            color={ARCHETYPE_COLORS[p.archetype] || 'var(--accent)'}
          />
        ))}
      </Card>

      {/* Per-archetype business cards */}
      {personas.map((p, i) => (
        <BizPersonaCard key={p.archetype} persona={p} rank={i} />
      ))}
    </div>
  )
}

function BizPersonaCard({ persona, rank }) {
  const color = ARCHETYPE_COLORS[persona.archetype] || 'var(--accent)'
  const b = persona.business || persona

  const bpi = b.buying_power_index ?? 0
  const bpiColor = bpi > 65 ? 'var(--teal)' : bpi > 40 ? 'var(--gold)' : 'var(--coral)'

  return (
    <Card style={{ borderLeft: `3px solid ${color}`, animation: `fadeUp 0.45s ${rank * 0.08}s ease both` }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16, marginBottom: 18 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--ink-3)', marginBottom: 4 }}>
            Archetype {String.fromCharCode(65 + (rank || 0))} · {Math.round(persona.weight * 100)}% of market
          </div>
          <h3 style={{ fontFamily: 'var(--serif)', fontSize: '1.3rem', color }}>{persona.archetype}</h3>
          <p style={{ fontSize: 12.5, color: 'var(--ink-2)', marginTop: 6, lineHeight: 1.55 }}>{b.market_summary}</p>
        </div>

        {/* Buying power index */}
        <div style={{ textAlign: 'center', flexShrink: 0 }}>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.06em', color: 'var(--ink-3)', marginBottom: 4 }}>
            Buying power
          </div>
          <div style={{
            width: 70, height: 70,
            borderRadius: '50%',
            border: `3px solid ${bpiColor}`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexDirection: 'column',
          }}>
            <span style={{ fontSize: 20, fontFamily: 'var(--mono)', fontWeight: 500, color: bpiColor, lineHeight: 1 }}>{bpi.toFixed(0)}</span>
            <span style={{ fontSize: 9, color: 'var(--ink-3)', fontFamily: 'var(--mono)' }}>/100</span>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
        {Object.entries(b.headline_stats || {}).map(([k, v]) =>
          v ? <Stat key={k} label={k.replace(/_/g, ' ')} value={v} /> : null
        )}
      </div>

      {/* Two-col: industries + gaps */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 16 }}>
        <div>
          <SectionLabel>Dominant industries</SectionLabel>
          {(b.dominant_industries || []).length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {b.dominant_industries.map((ind, i) => (
                <div key={i} style={{
                  fontSize: 12.5, padding: '8px 12px',
                  background: 'var(--paper-2)',
                  borderRadius: 'var(--r)',
                  color: 'var(--ink-2)',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--ink-3)' }}>#{i+1}</span>
                  {ind}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>No industry data available.</p>
          )}
        </div>

        <div>
          <SectionLabel>Market gaps / whitespace</SectionLabel>
          {(b.market_gaps || []).length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {b.market_gaps.map((gap, i) => (
                <div key={i} style={{
                  fontSize: 12.5, padding: '8px 12px',
                  background: 'var(--gold-lt)',
                  borderRadius: 'var(--r)',
                  color: 'var(--gold)',
                  display: 'flex', alignItems: 'flex-start', gap: 8,
                }}>
                  <span style={{ fontFamily: 'var(--mono)', fontSize: 10, marginTop: 2 }}>↳</span>
                  {gap}
                </div>
              ))}
            </div>
          ) : (
            <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>No gaps identified.</p>
          )}
        </div>
      </div>

      {/* Location signals */}
      {(b.location_signals || []).length > 0 && (
        <>
          <SectionLabel>Location signals</SectionLabel>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {b.location_signals.map((s, i) => (
              <SignalBadge key={i} signal={s.signal} type={s.type} />
            ))}
          </div>
        </>
      )}
    </Card>
  )
}

function BizSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Card><Skel h={100} /></Card>
      <Card><Skel h={240} /></Card>
      <Card><Skel h={240} /></Card>
    </div>
  )
}
