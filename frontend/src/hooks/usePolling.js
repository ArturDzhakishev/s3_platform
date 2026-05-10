import { useEffect, useRef } from 'react'

/**
 * Вызывает fn каждые interval мс пока компонент смонтирован.
 * Автоматически останавливается при размонтировании.
 */
export function usePolling(fn, interval = 5000, enabled = true) {
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    if (!enabled) return
    fnRef.current()
    const id = setInterval(() => fnRef.current(), interval)
    return () => clearInterval(id)
  }, [interval, enabled])
}
