'use client'

import { useCallback, useRef, useState } from 'react'

let nextId = 0

/**
 * Message list and request state for the "Ask the docs" panel.
 * Each assistant message keeps the full typed response from /api/ask.
 */
export function useAsk() {
  const [messages, setMessages] = useState([])
  const [pending, setPending] = useState(false)
  const inFlight = useRef(false)

  const ask = useCallback(async question => {
    const text = question.trim()
    if (!text || inFlight.current) return
    inFlight.current = true
    setPending(true)
    setMessages(list => [...list, { id: ++nextId, role: 'user', text }])

    let reply
    try {
      const res = await fetch('/api/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      const body = await res.json().catch(() => null)
      reply =
        res.ok && body
          ? { role: 'assistant', result: body }
          : { role: 'error', text: body?.message || 'Something went wrong. Please try again.' }
    } catch {
      reply = { role: 'error', text: "Can't reach the docs assistant. Check your connection." }
    }
    setMessages(list => [...list, { id: ++nextId, ...reply }])
    inFlight.current = false
    setPending(false)
  }, [])

  return { messages, pending, ask }
}
