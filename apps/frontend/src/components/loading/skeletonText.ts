import type { Theme } from '@mui/material/styles';

/** Typography variants the page skeletons stand in for. */
export type SkeletonTextVariant =
  | 'h4'
  | 'h6'
  | 'bodyLReg'
  | 'bodyMReg'
  | 'bodySReg';

/**
 * Sizes a `variant="text"` Skeleton to the typography variant it replaces.
 *
 * MUI derives a text skeleton's height from its font size, so reading that
 * size off the theme keeps each placeholder line the same height as the real
 * text that lands in its place, and keeps it in step when a variant changes.
 */
export const skeletonTextSx = (variant: SkeletonTextVariant) => ({
  fontSize: (theme: Theme) => theme.typography[variant].fontSize,
});
