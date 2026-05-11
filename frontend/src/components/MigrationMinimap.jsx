import React from 'react'
import { Card, SectionLabel } from './ui.jsx'

/**
 * MigrationMinimap — static diagram showing regional mobility signals.
 * Uses residential_mobility and other directional indicators from CTData.
 * Not interactive — meant as a quick spatial read on migration dynamics.
 */

const DIRECTION_ARROWS = {
  "High inflow":    { symbol: "↘", color: "var(--teal)", label: "High inbound migration" },
  "Moderate inflow":{ symbol: "→", color: "var(--accent-2)", label: "Moderate inbound" },
  "Stable":         { symbol: "⇄", color: "var(--ink-3)", label: "Stable population" },
  "Outflow":        { symbol: "↗", color: "var(--coral)", label: "Net outmigration" },
}

// CT regions for context
const CT_REGIONS = {
  "Fairfield County": ["Greenwich", "Stamford", "Norwalk", "Westport", "Darien", "New Canaan", "Wilton", "Fairfield", "Bridgeport"],
  "Greater Hartford": ["Hartford", "West Hartford", "Glastonbury", "Simsbury", "Avon", "Farmington", "Newington", "Wethersfield"],
  "New Haven Area":   ["New Haven", "Hamden", "Milford", "Cheshire", "Wallingford", "North Haven", "Branford"],
  "Eastern CT":       ["Norwich", "New London", "Groton", "Windham", "Mansfield", "Storrs"],
  "Litchfield Hills": ["Torrington", "Waterbury", "Litchfield", "New Milford", "Danbury"],
}

function getMigrationSignal(data) {
  const mobility = data?.residential_mobility || 0
  const singleParent = data?.single_parent_families || 0
  const snap = data?.snap_recipients || 0

  if (mobility > 15) return "High inflow"
  if (mobility > 8) return "Moderate inflow"
  if (snap > 25 && mobility < 5) return "Outflow"
  return "Stable"
}

function getRegion(town) {
  for (const [region, towns] of Object.entries(CT_REGIONS)) {
    if (towns.includes(town)) return region
  }
  return "Other CT"
}

export default function MigrationMinimap({ town, data }) {
  if (!town || !data) return null

  const signal = getMigrationSignal(data)
  const region = getRegion(town)
  const arrow = DIRECTION_ARROWS[signal]

  const mobility = data?.residential_mobility
  const singleParent = data?.single_parent_families
  const snap = data?.snap_recipients
  const housing_permits = data?.housing_permits
  const formations = data?.business_formations

  return (
    <Card>
      <SectionLabel>Regional context & mobility dynamics</SectionLabel>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>

        {/* Migration signal */}
        <div>
          <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Migration signal
          </div>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '16px', background: 'var(--paper-2)', borderRadius: 'var(--r)',
            border: `1px solid ${arrow.color}22`,
          }}>
            <span style={{ fontSize: 36, lineHeight: 1 }}>{arrow.symbol}</span>
            <div>
              <div style={{ fontWeight: 500, fontSize: 14, color: arrow.color }}>{signal}</div>
              <div style={{ fontSize: 12, color: 'var(--ink-3)', marginTop: 2 }}>{arrow.label}</div>
            </div>
          </div>

          <div style={{ marginTop: 12 }}>
            <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
              Region
            </div>
            <div style={{
              padding: '10px 14px', background: 'var(--paper-2)',
              borderRadius: 'var(--r)', fontSize: 13,
            }}>
              <span style={{ fontWeight: 500 }}>{region}</span>
              <div style={{ fontSize: 11, color: 'var(--ink-3)', marginTop: 3 }}>
                {CT_REGIONS[region]?.filter(t => t !== town).slice(0, 3).join(", ")}
                {CT_REGIONS[region]?.length > 4 ? ` +${CT_REGIONS[region].length - 4} more` : ""}
              </div>
            </div>
          </div>
        </div>

        {/* Mobility indicators */}
        <div>
          <div style={{ fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
            Directional indicators
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>

            {mobility != null && (
              <MobilityBar
                label="Residential mobility"
                value={mobility}
                max={30}
                format={v => `${v.toFixed(1)}%`}
                color={mobility > 10 ? 'var(--teal)' : 'var(--accent)'}
                note="% moved in last year"
              />
            )}

            {housing_permits != null && (
              <MobilityBar
                label="Housing permits"
                value={housing_permits}
                max={500}
                format={v => v.toFixed(0)}
                color="var(--accent-2)"
                note="new units approved"
              />
            )}

            {formations != null && (
              <MobilityBar
                label="Business formations"
                value={formations}
                max={200}
                format={v => v.toFixed(0)}
                color="var(--gold)"
                note="new businesses"
              />
            )}

            {snap != null && (
              <MobilityBar
                label="SNAP recipients"
                value={snap}
                max={50}
                format={v => `${v.toFixed(1)}%`}
                color={snap > 20 ? 'var(--coral)' : 'var(--ink-3)'}
                note="economic stress indicator"
              />
            )}

          </div>
        </div>
      </div>

      {/* Context note */}
      <div style={{
        marginTop: 16, padding: '10px 14px',
        background: 'var(--paper-2)', borderRadius: 'var(--r)',
        fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)',
        lineHeight: 1.6,
      }}>
        Migration signals derived from ACS residential mobility, housing permits, and economic stress indicators.
        Data reflects most recent available vintage (2017-2020).
      </div>
    </Card>
  )
}

function MobilityBar({ label, value, max, format, color, note }) {
  const pct = Math.min((value / max) * 100, 100)
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
        <span style={{ fontSize: 11, color: 'var(--ink-2)' }}>{label}</span>
        <span style={{ fontSize: 11, fontFamily: 'var(--mono)', color }}>{format(value)}</span>
      </div>
      <div style={{ height: 5, background: 'var(--paper-3)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          width: `${pct}%`, height: '100%',
          background: color, borderRadius: 3,
          transition: 'width 0.6s cubic-bezier(.4,0,.2,1)',
        }} />
      </div>
      <div style={{ fontSize: 10, color: 'var(--ink-3)', marginTop: 2 }}>{note}</div>
    </div>
  )
}
