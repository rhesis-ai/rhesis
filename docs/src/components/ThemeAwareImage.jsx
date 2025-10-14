'use client'

import { useTheme } from 'next-themes'
import { useEffect, useState } from 'react'

/**
 * ThemeAwareImage Component
 *
 * Displays different images based on the current theme (light/dark).
 *
 * @param {Object} props - Component props
 * @param {string} props.lightSrc - Image source for light mode
 * @param {string} props.darkSrc - Image source for dark mode
 * @param {string} props.alt - Alt text for the image
 * @param {string} [props.className] - Optional CSS classes
 *
 * Usage:
 * ```jsx
 * <ThemeAwareImage
 *   lightSrc="/screenshots/dashboard-light.png"
 *   darkSrc="/screenshots/dashboard-dark.png"
 *   alt="Dashboard Screenshot"
 * />
 * ```
 */
export const ThemeAwareImage = ({ lightSrc, darkSrc, alt, className = '' }) => {
  const { theme, resolvedTheme } = useTheme()
  const [mounted, setMounted] = useState(false)

  // Prevent hydration mismatch by only rendering after mount
  useEffect(() => {
    setMounted(true)
  }, [])

  // Show light image during SSR and initial render
  if (!mounted) {
    return (
      <img
        src={lightSrc}
        alt={alt}
        className={className}
        style={{ width: '100%', height: 'auto', borderRadius: '8px' }}
      />
    )
  }

  const isDark = resolvedTheme === 'dark' || theme === 'dark'

  return (
    <div
      className={className}
      style={{
        backdropFilter: isDark ? 'drop-shadow(0 4px 8px rgba(255, 255, 255, 0.1))' : 'none',
        filter: isDark ? 'drop-shadow(0 4px 12px rgba(255, 255, 255, 0.15)) drop-shadow(0 2px 4px rgba(255, 255, 255, 0.1))' : 'none'
      }}
    >
      <img
        src={isDark ? darkSrc : lightSrc}
        alt={alt}
        style={{
          width: '100%',
          height: 'auto',
          borderRadius: '8px'
        }}
      />
    </div>
  )
}

export default ThemeAwareImage
