import type { Theme } from '@mui/material/styles';

/** WebGL clear color for embedding-atlas `colorScheme: "dark"` (clearColor 0,0,0,1). */
export const EMBEDDING_ATLAS_DARK_SURFACE = '#000000';

/** Match the embedding scatter canvas so panels and overlays do not show a color seam. */
export function getEmbeddingViewSurfaceBg(theme: Theme): string {
  return theme.palette.mode === 'dark'
    ? EMBEDDING_ATLAS_DARK_SURFACE
    : theme.palette.background.paper;
}
