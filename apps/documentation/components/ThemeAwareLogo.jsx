'use client'

import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'

function ThemeAwareLogo() {
  const { theme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // Prevent hydration mismatch by only rendering after mount
  useEffect(() => {
    setMounted(true)
  }, [])

  // Show default logo during SSR and initial render
  if (!mounted) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <img
          src="/logo/rhesis-logo-website.png"
          alt="Rhesis"
          style={{ height: '40px', width: 'auto' }}
        />
        <span
          style={{
            fontFamily: '"Sora", sans-serif',
            fontWeight: 600,
            fontSize: '1.1rem',
            color: '#2AA1CE',
            whiteSpace: 'nowrap',
          }}
        >
          Documentation
        </span>
      </div>
    )
  }

  const isDark = resolvedTheme === 'dark' || theme === 'dark'

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
      <img
        src={isDark ? '/logo/rhesis-logo-website-white.png' : '/logo/rhesis-logo-website.png'}
        alt="Rhesis"
        style={{ height: '40px', width: 'auto' }}
      />
      <span
        style={{
          fontFamily: '"Sora", sans-serif',
          fontWeight: 600,
          fontSize: '1.1rem',
          color: isDark ? '#3BC4F2' : '#2AA1CE',
          whiteSpace: 'nowrap',
        }}
      >
        Documentation
      </span>
    </div>
  )
}

export default ThemeAwareLogo
