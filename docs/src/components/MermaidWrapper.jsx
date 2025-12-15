'use client'

import { useTheme } from 'nextra-theme-docs'
import { useEffect, useRef, useState, memo } from 'react'
import mermaid from 'mermaid'

/**
 * Theme-aware Mermaid wrapper that uses OKLCH categorical colors
 * for consistent rendering across light and dark themes.
 *
 * This component manually controls Mermaid rendering to prevent
 * graphs from disappearing during theme transitions.
 *
 * The OKLCH colors are defined in globals.css with fixed lightness
 * and chroma to ensure theme-invariant contrast.
 */
function MermaidComponent({ chart }) {
  const { resolvedTheme } = useTheme()
  const [stableTheme, setStableTheme] = useState(resolvedTheme || 'light')
  const [svg, setSvg] = useState(null)
  const [isInitialRender, setIsInitialRender] = useState(true)
  const chartRef = useRef(chart)
  const themeRef = useRef(stableTheme)
  const renderIdRef = useRef(0)

  // Only update stable theme when it actually changes
  useEffect(() => {
    const currentTheme = resolvedTheme || 'light'
    if (currentTheme !== stableTheme) {
      setStableTheme(currentTheme)
    }
  }, [resolvedTheme, stableTheme])

  // Render Mermaid diagram
  useEffect(() => {
    // Skip if neither chart nor theme has changed
    // This prevents unnecessary re-renders but allows theme updates
    if (svg && chart === chartRef.current && stableTheme === themeRef.current) {
      return
    }

    chartRef.current = chart
    themeRef.current = stableTheme

    const renderMermaid = async () => {
      if (typeof window === 'undefined' || !chart) {
        return
      }

      // Increment render ID to ensure unique IDs for each render
      const renderId = `mermaid-${++renderIdRef.current}-${Date.now()}`

      try {
        // Get CSS variables for theme-aware properties
        const style = getComputedStyle(document.documentElement)

        // Helper function to convert OKLCH to hex for Mermaid compatibility
        const oklchToHex = oklchString => {
          // If it's already a hex color, return it
          if (oklchString.startsWith('#')) return oklchString

          // Create a temporary element to let the browser convert OKLCH to RGB
          const temp = document.createElement('div')
          temp.style.color = oklchString
          document.body.appendChild(temp)
          const rgb = getComputedStyle(temp).color
          document.body.removeChild(temp)

          // Convert rgb(r, g, b) to hex
          const match = rgb.match(/\d+/g)
          if (match && match.length >= 3) {
            const r = parseInt(match[0]).toString(16).padStart(2, '0')
            const g = parseInt(match[1]).toString(16).padStart(2, '0')
            const b = parseInt(match[2]).toString(16).padStart(2, '0')
            return `#${r}${g}${b}`
          }
          return oklchString // Fallback
        }

        const bg = oklchToHex(style.getPropertyValue('--mermaid-bg').trim())
        const text = oklchToHex(style.getPropertyValue('--mermaid-text').trim())
        const line = oklchToHex(style.getPropertyValue('--mermaid-line').trim())
        const nodeText = oklchToHex(style.getPropertyValue('--mermaid-node-text').trim())

        // OKLCH categorical colors - convert to hex
        const cat1 = oklchToHex(style.getPropertyValue('--mermaid-cat-1').trim())
        const cat2 = oklchToHex(style.getPropertyValue('--mermaid-cat-2').trim())
        const cat3 = oklchToHex(style.getPropertyValue('--mermaid-cat-3').trim())
        const cat4 = oklchToHex(style.getPropertyValue('--mermaid-cat-4').trim())
        const cat5 = oklchToHex(style.getPropertyValue('--mermaid-cat-5').trim())
        const cat6 = oklchToHex(style.getPropertyValue('--mermaid-cat-6').trim())
        const cat7 = oklchToHex(style.getPropertyValue('--mermaid-cat-7').trim())
        const cat8 = oklchToHex(style.getPropertyValue('--mermaid-cat-8').trim())

        // Initialize Mermaid with theme-specific configuration
        mermaid.initialize({
          startOnLoad: false,
          theme: 'base',
          themeVariables: {
            background: bg,
            mainBkg: bg,
            secondBkg: bg,
            tertiaryBkg: bg,
            textColor: text,
            lineColor: line,
            primaryColor: cat1,
            primaryTextColor: nodeText,
            primaryBorderColor: cat1,
            secondaryColor: cat2,
            secondaryTextColor: nodeText,
            secondaryBorderColor: cat2,
            tertiaryColor: cat3,
            tertiaryTextColor: nodeText,
            tertiaryBorderColor: cat3,
            noteBkgColor: cat4,
            noteTextColor: nodeText,
            noteBorderColor: cat4,
            edgeLabelBackground: bg,
            clusterBkg: bg,
            clusterBorder: line,
            actor0: cat1,
            actor1: cat2,
            actor2: cat3,
            actor3: cat4,
            actorTextColor: nodeText,
            pie1: cat1,
            pie2: cat2,
            pie3: cat3,
            pie4: cat4,
            pie5: cat5,
            pie6: cat6,
            pie7: cat7,
            pie8: cat8,
            labelColor: text,
            labelTextColor: nodeText,
            stroke: line,
          },
          flowchart: {
            useMaxWidth: true,
            htmlLabels: true,
          },
        })

        // Render the diagram
        // Replace escaped newlines with actual newlines for proper parsing
        const chartWithNewlines = chart.replace(/\\n/g, '\n')
        const { svg: renderedSvg } = await mermaid.render(renderId, chartWithNewlines)
        setSvg(renderedSvg)
        setIsInitialRender(false)
      } catch (error) {
        // eslint-disable-next-line no-console
        console.error('Error rendering Mermaid chart:', error)
        // Keep the previous SVG on error to prevent blank display
      }
    }

    renderMermaid()
  }, [chart, stableTheme, svg])

  // Show loading only on initial render
  if (isInitialRender && !svg) {
    return <div className="mermaid-loading" style={{ minHeight: '200px' }} />
  }

  // Keep displaying the SVG even during re-renders
  // This prevents the graph from disappearing during theme transitions
  return <div className="mermaid" dangerouslySetInnerHTML={{ __html: svg || '' }} />
}

// Memoize the component to prevent unnecessary re-renders
// Only re-render if chart content changes
export const Mermaid = memo(MermaidComponent, (prevProps, nextProps) => {
  return prevProps.chart === nextProps.chart
})

// Default export for webpack alias compatibility
export default Mermaid
