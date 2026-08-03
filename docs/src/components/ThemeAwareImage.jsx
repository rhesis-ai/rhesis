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

  // The shadow tokens already flip with the theme, so the same style works in both.
  // A black shadow disappears against the dark canvas, hence the border to keep the
  // screenshot's edge readable there.
  const imageStyle = {
    width: '100%',
    height: 'auto',
    marginTop: '1.5rem',
    borderRadius: '8px',
    border: '1px solid var(--rh-border)',
    boxShadow: 'var(--rh-shadow-card)',
  }

  // Show light image during SSR and initial render
  if (!mounted) {
    return <img src={lightSrc} alt={alt} className={className} style={imageStyle} />
  }

  const isDark = resolvedTheme === 'dark' || theme === 'dark'

  return (
    <img src={isDark ? darkSrc : lightSrc} alt={alt} className={className} style={imageStyle} />
  )
}

export default ThemeAwareImage
