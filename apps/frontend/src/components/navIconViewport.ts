/** Fit a Figma path (nativeWidth × nativeHeight) into 20×20, centered in 24×24. */
const VIEW_SIZE = 24;
const DRAW_SIZE = 20;

export function getNavIconViewport(nativeWidth: number, nativeHeight: number) {
  const scale = DRAW_SIZE / Math.max(nativeWidth, nativeHeight);
  const scaledWidth = nativeWidth * scale;
  const scaledHeight = nativeHeight * scale;
  const offsetX = (VIEW_SIZE - scaledWidth) / 2;
  const offsetY = (VIEW_SIZE - scaledHeight) / 2;

  return {
    viewBox: `0 0 ${VIEW_SIZE} ${VIEW_SIZE}` as const,
    transform: `translate(${offsetX}, ${offsetY}) scale(${scale})`,
  };
}
