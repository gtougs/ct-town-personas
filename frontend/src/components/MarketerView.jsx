import React from 'react'
import { Card, Stat, WeightBar, SignalBadge, SectionLabel, Skel } from './ui.jsx'

const ARCHETYPE_COLORS = {
  'Affluent Suburban':        '#1a3a5c',
  'Working-Class Urban':      '#6b3a2a',
  'Rural / Small Town':       '#2a4a2a',
  'Young Professional':       '#2d3a6b',
  'Mixed-Income Transitional':'#5a3a6b',
}

export default function MarketerView({ data, loading }) {
  if (loading) return <MarketerSkeleton />
  if (!data) return null

  const personas = data.personas || []

  return (
    <div className="fade-up" style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Archetype weight overview */}
      <Card>
        <SectionLabel>Audience composition</SectionLabel>
        {personas.map(p => (
          <WeightBar
            key={p.archetype}
            label={p.archetype}
            weight={p.weight}
            color={ARCHETYPE_COLORS[p.archetype] || 'var(--accent)'}
          />
        ))}
        <p style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 12, fontStyle: 'italic' }}>
          Weights reflect GMM probability — town may contain multiple distinct audience segments.
        </p>
      </Card>

      {/* Per-persona cards */}
      {personas.map((p, i) => (
        <PersonaCard key={p.archetype} persona={p} rank={i} />
      ))}
    </div>
  )
}

function PersonaCard({ persona, rank }) {
  const color = ARCHETYPE_COLORS[persona.archetype] || 'var(--accent)'
  const m = persona.marketer || persona  // handle both full and marketer-only payloads

  return (
    <Card style={{ borderLeft: `3px solid ${color}`, animation: `fadeUp 0.45s ${rank * 0.08}s ease both` }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 16, gap: 12 }}>
        <div>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--ink-3)', marginBottom: 4 }}>
            Archetype {String.fromCharCode(65 + (rank || 0))}
          </div>
          <h3 style={{ fontFamily: 'var(--serif)', fontSize: '1.3rem', color }}>{persona.archetype}</h3>
          <p style={{ fontSize: 12.5, color: 'var(--ink-2)', marginTop: 6, lineHeight: 1.55 }}>
            {m.description}
          </p>
        </div>
        <div style={{
          fontFamily: 'var(--mono)', fontSize: 22, fontWeight: 500,
          color, background: `${color}12`,
          padding: '6px 14px', borderRadius: 'var(--r)',
          flexShrink: 0, lineHeight: 1,
        }}>
          {Math.round(persona.weight * 100)}%
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 20 }}>
        {Object.entries(m.headline_stats || {}).map(([k, v]) =>
          v ? <Stat key={k} label={k.replace(/_/g, ' ')} value={v} /> : null
        )}
      </div>

      {/* Two-col layout: signals + angles */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        <div>
          <SectionLabel>Audience signals</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(m.audience_signals || []).map((s, i) => (
              <SignalBadge key={i} signal={s.signal} strength={s.strength} />
            ))}
            {(m.audience_signals || []).length === 0 && (
              <p style={{ fontSize: 12, color: 'var(--ink-3)' }}>No signals available.</p>
            )}
          </div>
        </div>

        <div>
          <SectionLabel>Messaging angles</SectionLabel>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {(m.messaging_angles || []).map((angle, i) => (
              <div key={i} style={{
                fontSize: 12.5, padding: '8px 12px',
                background: 'var(--paper-2)',
                borderRadius: 'var(--r)',
                lineHeight: 1.5, color: 'var(--ink-2)',
                borderLeft: '2px solid var(--paper-3)',
              }}>
                {angle}
              </div>
            ))}
          </div>

          {/* Channel guidance */}
          {m.channel_guidance && (
            <>
              <SectionLabel style={{ marginTop: 16 }}>Channels</SectionLabel>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {Object.entries(m.channel_guidance).map(([ch, val]) => (
                  <div key={ch} style={{
                    fontSize: 11, fontFamily: 'var(--mono)',
                    padding: '4px 9px', borderRadius: 20,
                    background: val === 'high' ? `${color}18` : 'var(--paper-2)',
                    color: val === 'high' ? color : 'var(--ink-3)',
                    border: `0.5px solid ${val === 'high' ? `${color}40` : 'var(--paper-3)'}`,
                  }}>
                    {ch.replace(/_/g, ' ')} · {val}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {m.new_resident_opportunity && (
        <div style={{
          marginTop: 16, padding: '10px 14px',
          background: 'var(--gold-lt)',
          borderRadius: 'var(--r)',
          fontSize: 12.5, color: 'var(--gold)',
          fontFamily: 'var(--mono)',
        }}>
          ★ New resident opportunity: {m.new_resident_opportunity}
        </div>
      )}
    </Card>
  )
}

function MarketerSkeleton() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <Card><Skel h={120} /></Card>
      <Card><Skel h={200} /></Card>
      <Card><Skel h={200} /></Card>
    </div>
  )
}
