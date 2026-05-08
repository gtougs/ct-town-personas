const BASE = '/api'

async function get(path) {
  const res = await fetch(`${BASE}${path}`)
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
  return res.json()
}

export const api = {
  towns:       ()                        => get('/towns-list'),
  personas:    (town, year)              => get(`/personas/${town}${year ? `?year=${year}` : ''}`),
  marketer:    (town, year)              => get(`/personas/${town}/marketer${year ? `?year=${year}` : ''}`),
  business:    (town, year)              => get(`/personas/${town}/business${year ? `?year=${year}` : ''}`),
  similar:     (town, n = 5)            => get(`/personas/similar/${town}?n=${n}`),
  forecast:    (town, indicator)        => get(`/forecast/${town}/${indicator}`),
  allForecasts:(town)                   => get(`/forecast/${town}`),
  archetypes:  (year)                   => get(`/towns/archetypes/all${year ? `?year=${year}` : ''}`),
  compare:     (town, compareTo, year)  => get(`/towns/${town}/compare?compare_to=${compareTo}${year ? `&year=${year}` : ''}`),
}
