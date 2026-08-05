import type { PaletteMode } from '@mui/material/styles';

/**
 * `palette.background.default` per mode.
 *
 * Lives outside `theme.ts` because that file is `'use client'`: importing a
 * value from it into a Server Component yields a client reference rather than
 * the value, which silently rendered `background-color:undefined`. The root
 * layout is a Server Component and needs these as literal CSS in its pre-paint
 * <style> block, so they have to come from a plain module.
 *
 * `theme.ts` builds both palettes from these, so the pre-paint background and
 * the hydrated one cannot drift apart.
 */
export const BACKGROUND_DEFAULT: Record<PaletteMode, string> = {
  light: '#FFFFFF', // Intentional: needed as a literal before the theme exists
  dark: '#0D1117', // Intentional: needed as a literal before the theme exists
};
