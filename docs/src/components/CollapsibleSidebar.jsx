'use client'

import { useEffect } from 'react'
import { usePathname } from 'next/navigation'

function applySidebarState() {
  const headers = document.querySelectorAll('.rhesis-sidebar-section-header')

  headers.forEach(headerEl => {
    const li = headerEl.closest('li')
    if (!li) return

    const key = `sidebar-collapsed-${headerEl.textContent.trim()}`
    const collapsed = localStorage.getItem(key) === 'true'

    headerEl.classList.toggle('sidebar-collapsed', collapsed)

    let next = li.nextElementSibling
    while (next && !next.querySelector('.rhesis-sidebar-section-header')) {
      next.style.display = collapsed ? 'none' : ''
      next = next.nextElementSibling
    }
  })
}

export default function CollapsibleSidebar() {
  const pathname = usePathname()

  useEffect(() => {
    const timer = setTimeout(applySidebarState, 50)
    return () => clearTimeout(timer)
  }, [pathname])

  useEffect(() => {
    function handleClick(e) {
      const header = e.target.closest('.rhesis-sidebar-section-header')
      if (!header) return

      const key = `sidebar-collapsed-${header.textContent.trim()}`
      const current = localStorage.getItem(key) === 'true'
      localStorage.setItem(key, String(!current))
      applySidebarState()
    }

    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  return null
}
