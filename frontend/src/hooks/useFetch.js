import { useState, useEffect, useRef } from 'react'

export function useFetch(fn, deps = []) {
  const [data, setData]       = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState(null)
  const abortRef              = useRef(null)

  useEffect(() => {
    if (!fn) return
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setLoading(true)
    setError(null)

    fn()
      .then(d => { if (!controller.signal.aborted) { setData(d); setLoading(false) } })
      .catch(e => { if (!controller.signal.aborted) { setError(e.message); setLoading(false) } })

    return () => controller.abort()
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  return { data, loading, error }
}
