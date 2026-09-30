'use client'

import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useAsk } from './useAsk'
import styles from './AskDocs.module.css'

const ROUTE_LABELS = {
  answered: 'Answered from the docs',
  partially_answered: 'Partly covered by the docs',
  not_documented: 'Not in the docs',
  false_premise: 'Correction',
  needs_clarification: 'Needs clarification',
  out_of_scope: 'Out of scope',
  account_or_support: 'Support',
  unsafe_or_injection: 'Declined',
  smalltalk: 'Docs assistant',
}

function AssistantMessage({ result }) {
  return (
    <div className={styles.assistant}>
      <span className={styles.route}>{ROUTE_LABELS[result.route] || result.route}</span>
      <div className={styles.markdown}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.response}</ReactMarkdown>
      </div>
    </div>
  )
}

function Message({ message }) {
  if (message.role === 'user') return <div className={styles.user}>{message.text}</div>
  if (message.role === 'error') return <div className={styles.error}>{message.text}</div>
  return <AssistantMessage result={message.result} />
}

export default function AskDocs() {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState('')
  const { messages, pending, ask } = useAsk()
  const listRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight })
  }, [messages, pending])

  function submit(event) {
    event.preventDefault()
    if (!draft.trim() || pending) return
    ask(draft)
    setDraft('')
  }

  function onKeyDown(event) {
    if (event.key === 'Enter' && !event.shiftKey) submit(event)
    if (event.key === 'Escape') setOpen(false)
  }

  return (
    <>
      {open && (
        <section className={styles.panel} role="dialog" aria-label="Ask the docs">
          <header className={styles.header}>
            <span>Ask the docs</span>
            <button
              type="button"
              className={styles.close}
              onClick={() => setOpen(false)}
              aria-label="Close"
            >
              ×
            </button>
          </header>
          <div className={styles.messages} ref={listRef} aria-live="polite">
            {messages.length === 0 && (
              <p className={styles.hint}>
                Ask a question about Rhesis. Answers come from these docs, with links to the pages
                they're based on.
              </p>
            )}
            {messages.map(message => (
              <Message key={message.id} message={message} />
            ))}
            {pending && <p className={styles.hint}>Checking the docs…</p>}
          </div>
          <form className={styles.form} onSubmit={submit}>
            <textarea
              ref={inputRef}
              className={styles.input}
              value={draft}
              onChange={event => setDraft(event.target.value)}
              onKeyDown={onKeyDown}
              placeholder="How do I install the SDK?"
              rows={2}
              aria-label="Your question"
            />
            <button type="submit" className={styles.send} disabled={pending || !draft.trim()}>
              Ask
            </button>
          </form>
        </section>
      )}
      <button
        type="button"
        className={styles.launcher}
        onClick={() => setOpen(value => !value)}
        aria-expanded={open}
      >
        Ask the docs
      </button>
    </>
  )
}
