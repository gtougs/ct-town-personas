import React from 'react'

/* ── Stat pill ────────────────────────────────────────────────────────────── */
export function Stat({ label, value, accent }) {
  return (
    <div style={{
      display: 'flex', flexDirection: 'column', gap: 2,
      padding: '10px 14px',
      background: accent ? 'var(--accent)' : 'var(--paper-2)',
      borderRadius: 'var(--r)',
      border: `0.5px solid ${accent ? 'transparent' : 'var(--paper-3)'}`,
      minWidth: 110,
    }}>
      <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: accent ? 'rgba(255,255,255,0.65)' : 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>{label}</span>
      <span style={{ fontSize: 17, fontWeight: 500, color: accent ? '#fff' : 'var(--ink)', fontFamily: 'var(--mono)', letterSpacing: '-0.02em' }}>{value ?? '—'}</span>
    </div>
  )
}

/* ── Weight bar (archetype probability) ──────────────────────────────────── */
export function WeightBar({ label, weight, color = 'var(--accent)' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
      <span style={{ fontSize: 12, color: 'var(--ink-2)', minWidth: 160, fontFamily: 'var(--sans)' }}>{label}</span>
      <div style={{ flex: 1, height: 6, background: 'var(--paper-3)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          width: `${Math.round(weight * 100)}%`, height: '100%',
          background: color, borderRadius: 3,
          transition: 'width 0.6s cubic-bezier(.4,0,.2,1)',
        }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)', minWidth: 36, textAlign: 'right' }}>
        {Math.round(weight * 100)}%
      </span>
    </div>
  )
}

/* ── Signal badge ─────────────────────────────────────────────────────────── */
export function SignalBadge({ signal, strength, type }) {
  const colors = {
    high:     { bg: 'var(--accent)',   text: '#fff' },
    medium:   { bg: 'var(--paper-3)', text: 'var(--ink-2)' },
    positive: { bg: 'var(--teal-lt)', text: 'var(--teal)' },
    caution:  { bg: 'var(--coral-lt)',text: 'var(--coral)' },
    neutral:  { bg: 'var(--paper-3)', text: 'var(--ink-2)' },
  }
  const key = type || strength || 'medium'
  const { bg, text } = colors[key] || colors.medium

  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 8,
      padding: '8px 12px',
      background: bg, color: text,
      borderRadius: 'var(--r)',
      fontSize: 12, lineHeight: 1.45,
    }}>
      <span style={{ marginTop: 1 }}>{type === 'positive' ? '↑' : type === 'caution' ? '!' : '·'}</span>
      <span>{signal}</span>
    </div>
  )
}

/* ── Section header ───────────────────────────────────────────────────────── */
export function SectionLabel({ children }) {
  return (
    <div style={{
      fontSize: 10, fontFamily: 'var(--mono)', textTransform: 'uppercase',
      letterSpacing: '0.1em', color: 'var(--ink-3)',
      paddingBottom: 8, borderBottom: '0.5px solid var(--paper-3)',
      marginBottom: 14,
    }}>
      {children}
    </div>
  )
}

/* ── Skeleton loader ──────────────────────────────────────────────────────── */
export function Skel({ h = 20, w = '100%', mb = 8 }) {
  return <div className="skeleton" style={{ height: h, width: w, marginBottom: mb }} />
}

/* ── Card wrapper ─────────────────────────────────────────────────────────── */
export function Card({ children, style = {} }) {
  return (
    <div style={{
      background: 'var(--paper)',
      border: '0.5px solid var(--paper-3)',
      borderRadius: 'var(--r-lg)',
      padding: '20px 22px',
      ...style,
    }}>
      {children}
    </div>
  )
}

/* ── Tab bar ──────────────────────────────────────────────────────────────── */
export function Tabs({ tabs, active, onChange }) {
  return (
    <div style={{
      display: 'flex', gap: 2,
      background: 'var(--paper-2)',
      padding: 4, borderRadius: 'var(--r-lg)',
      border: '0.5px solid var(--paper-3)',
    }}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            flex: 1, padding: '8px 18px',
            background: active === t.id ? 'var(--paper)' : 'transparent',
            border: active === t.id ? '0.5px solid var(--paper-3)' : '0.5px solid transparent',
            borderRadius: 8,
            fontFamily: 'var(--sans)', fontSize: 13, fontWeight: active === t.id ? 500 : 400,
            color: active === t.id ? 'var(--ink)' : 'var(--ink-3)',
            cursor: 'pointer', transition: 'all 0.2s',
            letterSpacing: '-0.01em',
          }}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

/* ── Trend indicator ──────────────────────────────────────────────────────── */
export function TrendBadge({ direction, magnitude }) {
  const icons   = { increasing: '↑', decreasing: '↓', stable: '→' }
  const colors  = { increasing: 'var(--teal)', decreasing: 'var(--coral)', stable: 'var(--ink-3)' }
  const weights = { strong: 600, moderate: 500, weak: 400 }

  return (
    <span style={{
      fontFamily: 'var(--mono)', fontSize: 11,
      color: colors[direction] || 'var(--ink-3)',
      fontWeight: weights[magnitude] || 400,
    }}>
      {icons[direction]} {direction} ({magnitude})
    </span>
  )
}
