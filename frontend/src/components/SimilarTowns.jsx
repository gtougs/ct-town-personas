import React from 'react'
import { Card, SectionLabel, Skel } from './ui.jsx'
import { useFetch } from '../hooks/useFetch.js'
import { api } from '../api.js'

export default function SimilarTowns({ town, onSelect }) {
  const { data, loading } = useFetch(
    town ? () => api.similar(town) : null,
    [town]
  )

  if (!town) return null

  return (
    <Card>
      <SectionLabel>Similar towns by cluster proximity</SectionLabel>
      {loading && <Skel h={120} />}
      {data && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {data.similar_towns?.map(t => (
            <button
              key={t.town}
              onClick={() => onSelect(t.town)}
              style={{
                padding: '8px 14px',
                background: 'var(--paper-2)',
                border: '0.5px solid var(--paper-3)',
                borderRadius: 'var(--r)',
                cursor: 'pointer',
                textAlign: 'left',
                transition: 'all 0.15s',
              }}
              onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent)'}
              onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--paper-3)'}
            >
              <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--ink)' }}>{t.town}</div>
              <div style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--ink-3)', marginTop: 2 }}>
                {t.archetype_label}
              </div>
            </button>
          ))}
        </div>
      )}
    </Card>
  )
}
