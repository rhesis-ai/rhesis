import { useMemo } from 'react';
import { useTheme } from '@mui/material';
import type { Theme } from '@mui/material/styles';
import type { CellState } from './verdict-model';

export type DensityMode = 'numbers' | 'shape' | 'detail';

// Seven tracks, fixed order in every mode: name, total, passed, failed,
// passRate, status, strip. Modes only resize columns -- nothing is added,
// removed, or reordered, so a metric name never moves vertically or
// horizontally when the mode changes. Status collapses in Detail, where the
// per-test strip already answers the same question at full resolution.
//
// The status track is sized to hold "Needs Review" -- the longest band label
// -- at the theme's chip padding without ellipsis.
export const COLUMN_TEMPLATES: Record<DensityMode, string> = {
  numbers: '1fr 58px 66px 58px 78px 128px 0px',
  shape: '1fr 0px 66px 58px 78px 128px 230px',
  detail: '252px 0px 0px 52px 0px 0px 1fr',
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

// Small inline metadata icons -- info tooltip, drilldown, override
// indicator -- share one size across every card/row that renders one.
export const INLINE_ICON_SIZE = 14;

// Legend swatch square, same across every state chip in the legend row.
export const LEGEND_SWATCH_SIZE = 10;

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
    const info = theme.palette.info.main;
    const border = theme.palette.greyscale.border;
    const surface2 = theme.palette.greyscale.surface2;
    const label = theme.palette.greyscale.label;

    // Cells are alpha-blended straight onto the card background (no opaque
    // per-cell backdrop). In dark mode that background sits very close to
    // both `border` and `surface2`, so at low alpha those cells were nearly
    // invisible. `label` is much lighter and has real separation from it,
    // and swapping `pending` to `border` (still muted, but lighter than
    // `surface2`) restores its contrast too.
    const pendingColor = isDark ? border : surface2;
    const naColor = isDark ? label : border;

    return {
      pending: { color: pendingColor, alpha: isDark ? 0.5 : 0.6 },
      passed: { color: success, alpha: isDark ? 0.85 : 0.9 },
      failed: { color: error, alpha: isDark ? 0.85 : 0.9 },
      // 'scored' ("No verdict" in the UI) is permanent, not provisional -- a
      // metric with no pass/fail threshold configured will never resolve to
      // green or red. It gets its own hue (info blue) rather than sharing
      // warning with the in-flight states below: sharing amber would read as
      // "still being judged" for a result that is actually final.
      scored: { color: info, alpha: isDark ? 0.7 : 0.8 },
      error: { color: error, alpha: isDark ? 0.5 : 0.6 },
      na: { color: naColor, alpha: isDark ? 0.5 : 0.35 },
      // The two in-flight bands are deliberately far apart and never overlap
      // once the pulse depths in verdict-strip-render are applied: generating
      // stays dim so it can't compete with resolved cells, evaluating stays
      // bright. That separation is what makes the phase readable at a glance.
      generating: { color: warning, alpha: isDark ? 0.3 : 0.38 },
      evaluating: { color: warning, alpha: isDark ? 0.85 : 0.9 },
    };
  }, [theme, isDark]);
}
