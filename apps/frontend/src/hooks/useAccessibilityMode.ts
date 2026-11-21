import { useTheme } from '@mui/material/styles';

/**
 * True when the organisation (or deployment) turned on the accessibility mode
 * (`accessible_colors` / `BRAND_ACCESSIBLE_COLORS`). Extra safeguards such as
 * confirming reversible removals only apply then, so the default product
 * behaves as before.
 */
export function useAccessibilityMode(): boolean {
  return Boolean(useTheme().palette.accessibleColors);
}
