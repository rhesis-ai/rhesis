'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

/**
 * Accessibility gaps in markup the docs theme renders, which its props can't
 * reach. Runs after each navigation.
 */
export function ThemeA11yFixes() {
  const pathname = usePathname()

  useEffect(() => {
    const apply = () => {
      // Wide tables scroll sideways; only those become a tab stop (WCAG 2.1.1).
      document.querySelectorAll('main table').forEach(table => {
        if (table.scrollWidth > table.clientWidth + 1) {
          table.setAttribute('tabindex', '0')
        } else {
          table.removeAttribute('tabindex')
        }
      })
      // The menu button next to "Copy page" has only an icon (WCAG 4.1.2).
      document.querySelectorAll('button[aria-haspopup="listbox"]').forEach(button => {
        if (!button.hasAttribute('aria-label') && !button.title && !button.textContent.trim()) {
          button.setAttribute('aria-label', 'More copy options')
        }
      })
    }
    apply()
    const observer = new ResizeObserver(apply)
    observer.observe(document.body)
    return () => observer.disconnect()
  }, [pathname])

  return null
}

export default ThemeA11yFixes
