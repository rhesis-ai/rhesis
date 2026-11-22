'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

/**
 * Accessibility gaps in markup the docs theme renders, which its props can't
 * reach. Runs after each navigation.
 */
/** The table or its nearest ancestor inside main that scrolls sideways, if any. */
function scrollContainer(table) {
  for (let el = table; el && el.tagName !== 'MAIN'; el = el.parentElement) {
    const { overflowX } = getComputedStyle(el)
    if ((overflowX === 'auto' || overflowX === 'scroll') && el.scrollWidth > el.clientWidth + 1) {
      return el
    }
  }
  return null
}

export function ThemeA11yFixes() {
  const pathname = usePathname()

  useEffect(() => {
    const apply = () => {
      // Wide tables scroll sideways, in the table itself or in a wrapper. Only
      // the element that actually scrolls becomes a tab stop (WCAG 2.1.1).
      document.querySelectorAll('main table').forEach(table => {
        const scroller = scrollContainer(table)
        if (scroller) scroller.setAttribute('tabindex', '0')
      })
      // The menu button next to "Copy page" has only an icon (WCAG 4.1.2).
      document.querySelectorAll('button[aria-haspopup="listbox"]').forEach(button => {
        const copyPage = Array.from(button.parentElement?.children ?? []).some(
          el => el !== button && el.textContent.trim() === 'Copy page'
        )
        if (copyPage && !button.hasAttribute('aria-label') && !button.textContent.trim()) {
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
