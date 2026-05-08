import { useState, useEffect } from 'react'
import { api } from './api.js'
import { useFetch } from './hooks/useFetch.js'
import { Tabs, Skel } from './components/ui.jsx'
import MarketerView from './components/MarketerView.jsx'
import BusinessView from './components/BusinessView.jsx'
import ForecastPanel from './components/ForecastPanel.jsx'
import SimilarTowns from './components/SimilarTowns.jsx'

const TABS = [
  { id: 'marketer', label: '🎯 Marketer view' },
  { id: 'business', label: '📊 Business owner view' },
  { id: 'forecast', label: '📈 Trends & forecast' },
]

export default function App() {
  const [town, setTown]         = useState('')
  const [inputVal, setInputVal] = useState('')
  const [year, setYear]         = useState(null)
  const [tab, setTab]           = useState('marketer')
  const [showDropdown, setShowDropdown] = useState(false)

  const { data: meta } = useFetch(() => api.towns(), [])

  const towns = meta?.towns || []
  const years = meta?.years || []

  const filtered = inputVal.length > 1
    ? towns.filter(t => t.toLowerCase().includes(inputVal.toLowerCase())).slice(0, 8)
    : []

  const { data: personaData, loading: personaLoading } = useFetch(
    town ? () => api.personas(town, year) : null,
    [town, year]
  )

  function selectTown(t) {
    setTown(t)
    setInputVal(t)
    setShowDropdown(false)
  }

  useEffect(() => {
    if (years.length && !year) setYear(Math.max(...years))
  }, [years])

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <header style={{
        borderBottom: '0.5px solid var(--paper-3)',
        padding: '0 clamp(16px, 4vw, 48px)',
        background: 'var(--paper)',
        position: 'sticky', top: 0, zIndex: 100,
      }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', alignItems: 'center', gap: 24, height: 64 }}>
          <div style={{ flex: '0 0 auto' }}>
            <span style={{ fontFamily: 'var(--serif)', fontSize: '1.4rem', letterSpacing: '-0.02em' }}>
              CT<span style={{ color: 'var(--accent)' }}> Town</span> Personas
            </span>
          </div>

          {/* Town search */}
          <div style={{ flex: 1, maxWidth: 340, position: 'relative' }}>
            <input
              value={inputVal}
              onChange={e => { setInputVal(e.target.value); setShowDropdown(true) }}
              onFocus={() => setShowDropdown(true)}
              onBlur={() => setTimeout(() => setShowDropdown(false), 150)}
              placeholder="Search a Connecticut town..."
              style={{
                width: '100%', padding: '8px 14px',
                fontFamily: 'var(--sans)', fontSize: 13,
                background: 'var(--paper-2)',
                border: '0.5px solid var(--paper-3)',
                borderRadius: 'var(--r)', outline: 'none',
                color: 'var(--ink)',
                transition: 'border-color 0.2s',
              }}
              onMouseEnter={e => e.target.style.borderColor = 'var(--accent-2)'}
              onMouseLeave={e => e.target.style.borderColor = 'var(--paper-3)'}
            />
            {showDropdown && filtered.length > 0 && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 200,
                background: 'var(--paper)', border: '0.5px solid var(--paper-3)',
                borderRadius: 'var(--r)', marginTop: 4, overflow: 'hidden',
                boxShadow: '0 4px 24px rgba(0,0,0,0.08)',
              }}>
                {filtered.map(t => (
                  <div
                    key={t}
                    onMouseDown={() => selectTown(t)}
                    style={{
                      padding: '9px 14px', fontSize: 13, cursor: 'pointer',
                      color: 'var(--ink)', borderBottom: '0.5px solid var(--paper-2)',
                      transition: 'background 0.1s',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--paper-2)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
                  >
                    {t}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Year selector */}
          {years.length > 1 && (
            <select
              value={year || ''}
              onChange={e => setYear(Number(e.target.value))}
              style={{
                padding: '8px 12px', fontFamily: 'var(--mono)', fontSize: 12,
                background: 'var(--paper-2)', border: '0.5px solid var(--paper-3)',
                borderRadius: 'var(--r)', color: 'var(--ink)', cursor: 'pointer',
              }}
            >
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>
          )}

          <a
            href="https://www.ctdata.org"
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)', textDecoration: 'none', marginLeft: 'auto' }}
          >
            Data via CTData.org ↗
          </a>
        </div>
      </header>

      {/* ── Main ───────────────────────────────────────────────────────── */}
      <main style={{ flex: 1, padding: 'clamp(16px, 3vw, 40px) clamp(16px, 4vw, 48px)' }}>
        <div style={{ maxWidth: 1100, margin: '0 auto' }}>

          {!town && (
            <EmptyState towns={towns} onSelect={selectTown} />
          )}

          {town && (
            <>
              {/* Town header */}
              <div className="fade-in" style={{ marginBottom: 28 }}>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, flexWrap: 'wrap' }}>
                  <h1 style={{ fontFamily: 'var(--serif)' }}>{town}</h1>
                  {personaData?.dominant_archetype && (
                    <span style={{
                      fontSize: 12, fontFamily: 'var(--mono)', padding: '3px 10px',
                      background: 'var(--accent)', color: '#fff',
                      borderRadius: 20,
                    }}>
                      {personaData.dominant_archetype}
                    </span>
                  )}
                  {year && (
                    <span style={{ fontSize: 12, fontFamily: 'var(--mono)', color: 'var(--ink-3)' }}>
                      ACS {year}
                    </span>
                  )}
                </div>
                {personaData?.summary && (
                  <p style={{ fontSize: 13.5, color: 'var(--ink-2)', marginTop: 8, maxWidth: 640, lineHeight: 1.6 }}>
                    {personaData.summary}
                  </p>
                )}
              </div>

              {/* Tabs */}
              <div style={{ marginBottom: 24, maxWidth: 520 }}>
                <Tabs tabs={TABS} active={tab} onChange={setTab} />
              </div>

              {/* Tab content */}
              {tab === 'marketer' && (
                <MarketerView data={personaData} loading={personaLoading} />
              )}
              {tab === 'business' && (
                <BusinessView data={personaData} loading={personaLoading} />
              )}
              {tab === 'forecast' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                  <ForecastPanel town={town} />
                </div>
              )}

              {/* Similar towns — always visible */}
              <div style={{ marginTop: 28 }}>
                <SimilarTowns town={town} onSelect={selectTown} />
              </div>
            </>
          )}
        </div>
      </main>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <footer style={{
        borderTop: '0.5px solid var(--paper-3)',
        padding: '16px clamp(16px, 4vw, 48px)',
        fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)',
      }}>
        <div style={{ maxWidth: 1100, margin: '0 auto', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
          <span>CT Town Personas — built on CTData.org & data.ct.gov</span>
          <span>Data: ACS 5-yr estimates · CT SOTS Business Registry · Census Bureau</span>
        </div>
      </footer>
    </div>
  )
}

function EmptyState({ towns, onSelect }) {
  const featured = ['Greenwich', 'Hartford', 'New Haven', 'Stamford', 'Westport', 'Middletown']
    .filter(t => towns.includes(t))

  return (
    <div style={{ paddingTop: 48, textAlign: 'center' }}>
      <h2 style={{ fontFamily: 'var(--serif)', marginBottom: 12, color: 'var(--ink)' }}>
        Who will you <em>meet</em> there?
      </h2>
      <p style={{ fontSize: 14, color: 'var(--ink-3)', maxWidth: 480, margin: '0 auto 32px', lineHeight: 1.7 }}>
        Select any of Connecticut's 169 towns to see ML-generated audience personas,
        market intelligence, and demographic trend forecasts.
      </p>
      {featured.length > 0 && (
        <>
          <p style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>
            Start with
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, justifyContent: 'center' }}>
            {featured.map(t => (
              <button
                key={t}
                onClick={() => onSelect(t)}
                style={{
                  padding: '10px 20px',
                  fontFamily: 'var(--sans)', fontSize: 13, fontWeight: 500,
                  background: 'var(--paper-2)',
                  border: '0.5px solid var(--paper-3)',
                  borderRadius: 'var(--r)',
                  cursor: 'pointer', color: 'var(--ink)',
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = 'var(--accent)'; e.currentTarget.style.color = 'var(--accent)' }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'var(--paper-3)'; e.currentTarget.style.color = 'var(--ink)' }}
              >
                {t}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
