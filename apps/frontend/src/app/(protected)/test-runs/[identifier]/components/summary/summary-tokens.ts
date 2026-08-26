import { useMemo } from 'react';
import { useTheme } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import type { CellState } from './verdict-model';

export type DensityMode = 'numbers' | 'shape' | 'detail';

// Six tracks, fixed order in every mode: name, total, passed, failed,
// passRate, strip. Modes only resize columns -- nothing is added, removed,
// or reordered, so a metric name never moves vertically or horizontally
// when the mode changes.
export const COLUMN_TEMPLATES: Record<DensityMode, string> = {
  numbers: '1fr 58px 66px 58px 78px 0px',
  shape: '1fr 0px 66px 58px 78px 230px',
  detail: '252px 0px 0px 52px 0px 1fr',
};

export const STRIP_HEIGHTS: Record<DensityMode, number> = {
  numbers: 0,
  shape: 13,
  detail: 21,
};

export const ROLLUP_HEIGHT = 16;

export const LAST_COLUMN_LABEL: Record<DensityMode, string> = {
  numbers: '',
  shape: 'Distribution',
  detail: 'Every test',
};

// Raw px, not theme.spacing() multiples -- these are exact prototype
// geometry values, same precedent as GEOMETRY below.
export const GRID_GAP = 14;
export const GRID_PADDING_X = 18;

export const GEOMETRY = { rowHeight: 28, stripHeight: 20, gap: 1 } as const;
export const DURATIONS = { morph: 420, fade: 400, ring: 1400 } as const;

export function gridMorphTransition(
  theme: Theme,
  reducedMotion: boolean
): string {
  if (reducedMotion) return 'none';
  return `grid-template-columns ${DURATIONS.morph}ms ${theme.transitions.easing.easeInOut}`;
}

export function useVerdictPalette(): Record<
  CellState,
  { color: string; alpha: number }
> {
  const theme = useTheme();
  const isDark = theme.palette.mode === 'dark';

  return useMemo(() => {
    const success = theme.palette.success.main;
    const error = theme.palette.error.main;
    const warning = theme.palette.warning.main;
    const border = theme.palette.greyscale.border;
    const surface2 = theme.palette.greyscale.surface2;
    const label = theme.palette.greyscale.label;

    // Cells are alpha-blended straight onto the card background (no opaque
    // per-cell backdrop), which in dark mode is `#161B22` -- close to both
    // `border` (`#30363d`) and `surface2` (`#0d1117`), so at low alpha those
    // cells were nearly invisible. `label` (`#8b949e`) has real separation
    // from the dark background, and swapping `pending` to `border` (still
    // muted, but lighter than `surface2`) restores its contrast too.
    const pendingColor = isDark ? border : surface2;
    const naColor = isDark ? label : border;

    return {
      pending: { color: pendingColor, alpha: isDark ? 0.5 : 0.6 },
      passed: { color: success, alpha: isDark ? 0.85 : 0.9 },
      failed: { color: error, alpha: isDark ? 0.85 : 0.9 },
      scored: { color: warning, alpha: isDark ? 0.7 : 0.8 },
      error: { color: error, alpha: isDark ? 0.5 : 0.6 },
      na: { color: naColor, alpha: isDark ? 0.5 : 0.35 },
      inFlight: { color: warning, alpha: isDark ? 0.5 : 0.6 },
    };
  }, [theme, isDark]);
}
