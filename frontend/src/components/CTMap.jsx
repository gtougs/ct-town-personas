import React, { useEffect, useState, useCallback } from 'react'

const ARCHETYPE_COLORS = {
  "Mainstream CT Suburban":     "#5b7fa6",
  "Affluent Suburban":          "#5b7fa6",
  "Affluent Commuter Belt":     "#1a3a5c",
  "Working-Class Urban":        "#8b2e2e",
  "Distressed Urban":           "#8b2e2e",
  "Rural & Small Town":         "#3d6b3d",
  "Rural / Small Town":         "#3d6b3d",
  "Working & Middle Class":     "#6b7a3d",
  "Young Professional Hub":     "#2d3a8b",
  "Young Professional":         "#2d3a8b",
  "Urban Core":                 "#4a2d8b",
  "Mixed-Income Transitional":  "#7a3d8b",
  "Gold Coast Affluent":        "#1a3a5c",
}

const GEOJSON_URL = "/ct-towns.geojson"
const W = 700, H = 380

export default function CTMap({ onTownSelect, selectedTown }) {
  const [geoData, setGeoData]   = useState(null)
  const [geoError, setGeoError] = useState(false)
  const [tooltip, setTooltip]   = useState(null)

  const [allClusters, setAllClusters] = useState({})

  useEffect(() => {
    fetch('/api/towns/all-clusters')
      .then(r => r.json())
      .then(d => {
        const map = {}
        if (d.towns) {
          d.towns.forEach(({ town, archetype_label }) => {
            map[town] = archetype_label
          })
        }
        setAllClusters(map)
      })
      .catch(() => {})
  }, [])

  // Fetch GeoJSON
  useEffect(() => {
    fetch(GEOJSON_URL)
      .then(r => { if (!r.ok) throw new Error('Failed'); return r.json() })
      .then(setGeoData)
      .catch(() => setGeoError(true))
  }, [])

  const project = useCallback((lon, lat) => {
    // EPSG:2234 CT State Plane feet — use actual CT bounds
    const minX = 730512, maxX = 1263094
    const minY = 544019, maxY = 944279
    const x = ((lon - minX) / (maxX - minX)) * W
    const y = H - ((lat - minY) / (maxY - minY)) * H
    return [x, y]
  }, [])

  const ringToPath = useCallback((ring) =>
    ring.map((pt, i) => {
      const [x, y] = project(pt[0], pt[1])
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    }).join(' ') + ' Z'
  , [project])

  const featurePath = useCallback((feature) => {
    const geo = feature.geometry
    if (!geo) return ""
    if (geo.type === "Polygon") return geo.coordinates.map(ringToPath).join(' ')
    if (geo.type === "MultiPolygon") return geo.coordinates.map(poly => poly.map(ringToPath).join(' ')).join(' ')
    return ""
  }, [ringToPath])

  const getTownName = (props) => {
    if (!props) return ""
    const raw = props.TOWN_NAME || props?.NAME || props?.name || props?.TOWN || props?.town || ""
    return raw.trim().split(' ')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase()).join(' ')
  }

  const isCTTown = (props) => {
    return props?.STATE_NAME === 'Connecticut' || props?.STATE_COD === 'CT'
  }

  const getColor = (townName) => allClusters[townName]
    ? ARCHETYPE_COLORS[allClusters[townName]] || "#94a3b8"
    : "#ddd8ce"

  const legendItems = [...new Set(Object.values(allClusters))].map(label => ({
    label,
    color: ARCHETYPE_COLORS[label] || "#94a3b8",
  })).sort((a, b) => a.label.localeCompare(b.label))

  if (geoError) {
    return <FallbackGrid allClusters={allClusters} onTownSelect={onTownSelect} selectedTown={selectedTown} />
  }

  if (!geoData) {
    return (
      <div style={{ height: H, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--paper-2)', borderRadius: 'var(--r-lg)' }}>
        <p style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-3)' }}>Loading CT map...</p>
      </div>
    )
  }

  return (
    <div style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto' }}>
        {geoData.features?.map((feature, i) => {
          const townName = getTownName(feature.properties)
          const archetype = allClusters[townName]
          const isSelected = selectedTown === townName
          const d = featurePath(feature)
          if (!d) return null
          return (
            <path
              key={i} d={d}
              fill={getColor(townName)}
              stroke={isSelected ? "#fff" : "rgba(255,255,255,0.7)"}
              strokeWidth={isSelected ? 2 : 0.5}
              style={{ cursor: 'pointer', transition: 'opacity 0.15s' }}
              opacity={selectedTown && !isSelected ? 0.75 : 1}
              onClick={() => isCTTown(feature.properties) && onTownSelect && onTownSelect(townName)}
              onMouseEnter={e => {
                const rect = e.currentTarget.ownerSVGElement.getBoundingClientRect()
                setTooltip({ x: e.clientX - rect.left, y: e.clientY - rect.top, town: townName, archetype: archetype || "—" })
              }}
              onMouseLeave={() => setTooltip(null)}
            />
          )
        })}
      </svg>

      {tooltip && (
        <div style={{
          position: 'absolute', left: tooltip.x + 12, top: tooltip.y - 10,
          background: 'var(--ink)', color: '#fff',
          padding: '6px 10px', borderRadius: 'var(--r)',
          fontSize: 12, fontFamily: 'var(--sans)',
          pointerEvents: 'none', zIndex: 10, whiteSpace: 'nowrap',
          boxShadow: '0 4px 12px rgba(0,0,0,0.25)',
        }}>
          <div style={{ fontWeight: 500 }}>{tooltip.town}</div>
          <div style={{ opacity: 0.75, fontSize: 11 }}>{tooltip.archetype}</div>
        </div>
      )}

      {legendItems.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 12, justifyContent: 'center' }}>
          {legendItems.map(({ label, color }) => (
            <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-2)' }}>
              <div style={{ width: 10, height: 10, borderRadius: 2, background: color }} />
              {label}
            </div>
          ))}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 11, fontFamily: 'var(--mono)', color: 'var(--ink-3)' }}>
            <div style={{ width: 10, height: 10, borderRadius: 2, background: '#ddd8ce', border: '1px solid #ccc' }} />
            Loading...
          </div>
        </div>
      )}
    </div>
  )
}

function FallbackGrid({ allClusters, onTownSelect, selectedTown }) {
  const byArchetype = {}
  Object.entries(allClusters).forEach(([town, archetype]) => {
    if (!byArchetype[archetype]) byArchetype[archetype] = []
    byArchetype[archetype].push(town)
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {Object.entries(byArchetype).sort().map(([archetype, towns]) => (
        <div key={archetype}>
          <div style={{ fontSize: 10, fontFamily: 'var(--mono)', textTransform: 'uppercase', letterSpacing: '0.08em', color: ARCHETYPE_COLORS[archetype] || 'var(--ink-3)', marginBottom: 6 }}>
            {archetype} ({towns.length})
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {towns.map(town => (
              <button key={town} onClick={() => onTownSelect(town)} style={{
                padding: '3px 8px', fontSize: 11,
                background: selectedTown === town ? (ARCHETYPE_COLORS[archetype] || 'var(--accent)') : 'var(--paper-2)',
                color: selectedTown === town ? '#fff' : 'var(--ink)',
                border: '0.5px solid var(--paper-3)', borderRadius: 4, cursor: 'pointer',
              }}>
                {town}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  )
}
