'use client'

import React from 'react'

/**
 * ChatExchange — renders a conversation between a user and Architect.
 *
 * Usage in MDX:
 * <ChatExchange>
 *   <ChatUser>Your message here.</ChatUser>
 *   <ChatArchitect>Architect reply here.</ChatArchitect>
 * </ChatExchange>
 */

const avatarBase = {
  width: '1.75rem',
  height: '1.75rem',
  borderRadius: '50%',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  fontSize: '0.7rem',
  fontWeight: '700',
  flexShrink: 0,
  letterSpacing: '0.02em',
}

export const EngineeringIcon = ({ color }) => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 24 24"
    fill={color || 'currentColor'}
    width="1rem"
    height="1rem"
    style={{ display: 'inline', verticalAlign: 'middle', marginBottom: '0.1em' }}
  >
    <path d="M9 15c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4m-6 4c.22-.72 3.31-2 6-2 2.7 0 5.8 1.29 6 2zM4.74 9H5c0 2.21 1.79 4 4 4s4-1.79 4-4h.26c.27 0 .49-.22.49-.49v-.02c0-.27-.22-.49-.49-.49H13c0-1.48-.81-2.75-2-3.45v.95c0 .28-.22.5-.5.5s-.5-.22-.5-.5V4.14C9.68 4.06 9.35 4 9 4s-.68.06-1 .14V5.5c0 .28-.22.5-.5.5S7 5.78 7 5.5v-.95C5.81 5.25 5 6.52 5 8h-.26c-.27 0-.49.22-.49.49v.03c0 .26.22.48.49.48M11 9c0 1.1-.9 2-2 2s-2-.9-2-2zm10.98-2.77.93-.83-.75-1.3-1.19.39c-.14-.11-.3-.2-.47-.27L20.25 3h-1.5l-.25 1.22q-.255.105-.48.27l-1.18-.39-.75 1.3.93.83c-.02.17-.02.35 0 .52l-.93.85.75 1.3 1.2-.38c.13.1.28.18.43.25l.28 1.23h1.5l.27-1.22c.16-.07.3-.15.44-.25l1.19.38.75-1.3-.93-.85c.03-.19.02-.36.01-.53M19.5 7.75c-.69 0-1.25-.56-1.25-1.25s.56-1.25 1.25-1.25 1.25.56 1.25 1.25-.56 1.25-1.25 1.25m-.1 3.04-.85.28c-.1-.08-.21-.14-.33-.19l-.18-.88h-1.07l-.18.87c-.12.05-.24.12-.34.19l-.84-.28-.54.93.66.59c-.01.13-.01.25 0 .37l-.66.61.54.93.86-.27c.1.07.2.13.31.18l.18.88h1.07l.19-.87c.11-.05.22-.11.32-.18l.85.27.54-.93-.66-.61c.01-.13.01-.25 0-.37l.66-.59zm-1.9 2.6c-.49 0-.89-.4-.89-.89s.4-.89.89-.89.89.4.89.89-.4.89-.89.89" />
  </svg>
)

const bubbleBase = {
  maxWidth: '82%',
  padding: '0.6rem 0.9rem',
  borderRadius: '0.75rem',
  fontSize: '0.875rem',
  lineHeight: '1.6',
  whiteSpace: 'pre-wrap',
  wordBreak: 'break-word',
}

export const ChatUser = ({ children }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'flex-end',
      alignItems: 'flex-end',
      gap: '0.5rem',
      marginBottom: '0.75rem',
    }}
  >
    <div
      style={{
        ...bubbleBase,
        backgroundColor: 'var(--chat-user-bg, #d0eaf6)',
        color: 'var(--chat-user-text, #1a5f7a)',
        borderBottomRightRadius: '0.2rem',
      }}
    >
      {children}
    </div>
    <div
      style={{
        ...avatarBase,
        backgroundColor: 'var(--chat-user-avatar-bg, #a8d8ee)',
        color: '#1a5f7a',
      }}
    >
      U
    </div>
  </div>
)

export const ChatArchitect = ({ children }) => (
  <div
    style={{
      display: 'flex',
      justifyContent: 'flex-start',
      alignItems: 'flex-end',
      gap: '0.5rem',
      marginBottom: '0.75rem',
    }}
  >
    <div
      style={{
        ...avatarBase,
        backgroundColor: 'var(--chat-architect-avatar-bg, #e8f4f8)',
        color: 'var(--chat-architect-avatar-text, #2AA1CE)',
        border: '1px solid var(--chat-architect-avatar-border, #b8dff0)',
      }}
    >
      <EngineeringIcon color="var(--chat-architect-avatar-text, #2AA1CE)" />
    </div>
    <div
      style={{
        ...bubbleBase,
        backgroundColor: 'var(--chat-architect-bg, #f3f4f6)',
        color: 'var(--chat-architect-text, #374151)',
        borderBottomLeftRadius: '0.2rem',
        border: '1px solid var(--chat-architect-border, #e5e7eb)',
      }}
    >
      {children}
    </div>
  </div>
)

export const ChatExchange = ({ children, title }) => (
  <div
    style={{
      border: '1px solid var(--chat-container-border, #e5e7eb)',
      borderRadius: '0.75rem',
      padding: '1rem 1rem 0.25rem',
      marginTop: '1.25rem',
      marginBottom: '1.25rem',
      backgroundColor: 'var(--chat-container-bg, #fafafa)',
    }}
  >
    {title && (
      <div
        style={{
          fontSize: '0.72rem',
          color: 'var(--chat-title-color, #9ca3af)',
          marginBottom: '0.85rem',
        }}
      >
        {title}
      </div>
    )}
    {children}
  </div>
)

export default ChatExchange
