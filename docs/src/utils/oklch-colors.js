/**
 * OKLCH Categorical Color Palette Utility
 *
 * Generates theme-invariant categorical colors using OKLCH color space.
 * Colors maintain consistent contrast across light and dark themes.
 *
 * OKLCH provides perceptual uniformity:
 * - L (Lightness): 0-100%
 * - C (Chroma): 0-0.4 (saturation)
 * - H (Hue): 0-360 degrees
 *
 * Benefits:
 * - Identical colors in light & dark themes
 * - Stable colors for graphs, diagrams, React Flow
 * - Zero runtime theme branching
 * - Perceptually uniform spacing
 */

/**
 * Generate OKLCH categorical color palette
 * @param {number} count - Number of colors to generate
 * @param {number} lightness - Fixed lightness (0-100), default 65%
 * @param {number} chroma - Fixed chroma (0-0.4), default 0.25 for vivid colors
 * @param {number} hueStart - Starting hue angle (0-360), default 0
 * @returns {string[]} Array of OKLCH color strings
 */
export function generateOKLCHPalette(count = 8, lightness = 65, chroma = 0.25, hueStart = 0) {
  const colors = []
  const hueStep = 360 / count

  for (let i = 0; i < count; i++) {
    const hue = (hueStart + i * hueStep) % 360
    colors.push(`oklch(${lightness}% ${chroma} ${hue})`)
  }

  return colors
}

/**
 * Predefined categorical palette matching CSS variables
 * Fixed lightness (65%) and chroma (0.25) for vivid, consistent colors
 */
export const CATEGORICAL_COLORS = {
  cat1: 'oklch(65% 0.25 220)', // Blue
  cat2: 'oklch(65% 0.25 280)', // Purple
  cat3: 'oklch(65% 0.25 30)', // Orange
  cat4: 'oklch(65% 0.25 140)', // Green
  cat5: 'oklch(65% 0.25 350)', // Magenta
  cat6: 'oklch(65% 0.25 190)', // Cyan
  cat7: 'oklch(65% 0.25 60)', // Yellow-Orange
  cat8: 'oklch(65% 0.25 170)', // Teal
}

/**
 * Get categorical color by index (wraps around)
 * @param {number} index - Color index
 * @returns {string} OKLCH color string
 */
export function getCategoricalColor(index) {
  const colors = Object.values(CATEGORICAL_COLORS)
  return colors[index % colors.length]
}

/**
 * Get CSS variable reference for categorical color
 * @param {number} index - Color index (1-8)
 * @returns {string} CSS variable reference
 */
export function getCategoricalVar(index) {
  const num = ((index - 1) % 8) + 1
  return `var(--mermaid-cat-${num})`
}

/**
 * Convert OKLCH to RGB (approximate, for fallback support)
 * Note: This is a simplified conversion. For production, use a proper color library.
 * @param {number} l - Lightness (0-100)
 * @param {number} c - Chroma (0-0.4)
 * @param {number} h - Hue (0-360)
 * @returns {string} RGB color string
 */
export function oklchToRGB(l, c, h) {
  // This is a simplified approximation
  // For accurate conversion, use a library like culori or d3-color
  const hueRad = (h * Math.PI) / 180
  const a = c * Math.cos(hueRad)
  const b = c * Math.sin(hueRad)

  // Simplified LAB to RGB conversion (not accurate, just for fallback)
  const y = (l + 16) / 116
  const x = a / 500 + y
  const z = y - b / 200

  let r = x * 3.2406 + y * -1.5372 + z * -0.4986
  let g = x * -0.9689 + y * 1.8758 + z * 0.0415
  let bl = x * 0.0557 + y * -0.204 + z * 1.057

  r = r > 0.0031308 ? 1.055 * Math.pow(r, 1 / 2.4) - 0.055 : 12.92 * r
  g = g > 0.0031308 ? 1.055 * Math.pow(g, 1 / 2.4) - 0.055 : 12.92 * g
  bl = bl > 0.0031308 ? 1.055 * Math.pow(bl, 1 / 2.4) - 0.055 : 12.92 * bl

  r = Math.max(0, Math.min(255, Math.round(r * 255)))
  g = Math.max(0, Math.min(255, Math.round(g * 255)))
  bl = Math.max(0, Math.min(255, Math.round(bl * 255)))

  return `rgb(${r}, ${g}, ${bl})`
}

/**
 * Check if browser supports OKLCH
 * @returns {boolean} True if OKLCH is supported
 */
export function supportsOKLCH() {
  if (typeof window === 'undefined') return false

  try {
    const test = document.createElement('div')
    test.style.color = 'oklch(50% 0.1 180)'
    return test.style.color !== ''
  } catch {
    return false
  }
}

/**
 * Get color with fallback for browsers that don't support OKLCH
 * @param {string} oklchColor - OKLCH color string
 * @param {string} fallbackColor - Fallback RGB/hex color
 * @returns {string} Color string
 */
export function getColorWithFallback(oklchColor, fallbackColor) {
  return supportsOKLCH() ? oklchColor : fallbackColor
}
