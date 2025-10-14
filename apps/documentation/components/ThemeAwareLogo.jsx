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
      <img
        src="/logo/rhesis_logo_documentation.png"
        alt="Rhesis"
        style={{ height: '20px', width: 'auto' }}
      />
    )
  }

  const isDark = resolvedTheme === 'dark' || theme === 'dark'

  return (
    <img
      src={
        isDark ? '/logo/rhesis_logo_dark_documentation.png' : '/logo/rhesis_logo_documentation.png'
      }
      alt="Rhesis"
      style={{ height: '25px', width: 'auto' }}
    />
  )
}

export default ThemeAwareLogo
