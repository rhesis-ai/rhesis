'use client';

import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

/**
 * Suspense fallbacks are held invisible for this long before fading in.
 *
 * A skeleton predicts the shape of content that hasn't arrived. When the
 * prediction is wrong the swap reads as a glitch, and the worst case is a
 * page whose list is empty: a six-row table dissolves into an onboarding
 * card. Empty pages are also the fastest ones, since there is no data to
 * fetch or serialize, so they are exactly the pages that resolve inside this
 * window and never show a skeleton at all.
 *
 * Page headers are not held: `SkeletonPageHeader` draws a route's known title
 * and description at once, so the hold only covers what waits for data, and
 * `nextjs-toploader` shows progress from the click.
 *
 * 200ms is the common skeleton delay (long enough to skip a flash on a fast
 * response, short enough that a slow page shows its shape almost at once).
 * TanStack Router defaults the same knob (`defaultPendingMs`) to 1000ms for a
 * whole route with no header of its own; raise this if empty pages still
 * flash a skeleton in production.
 *
 * The complementary half of this pattern, a minimum display duration
 * (TanStack's `pendingMinMs`), is deliberately absent: React owns when it
 * unmounts a `loading.tsx` fallback, so honouring a minimum would mean
 * hand-rolled Suspense boundaries and client timers on every route. The fade
 * below softens that case instead, since a fallback unmounted mid-fade never
 * reached full opacity.
 */
export const SKELETON_DELAY_MS = 200;

/** Fade length once the delay has elapsed. Short enough to feel immediate. */
export const SKELETON_FADE_MS = 150;

export const delayedRevealSx = {
  opacity: 0,
  '@keyframes delayed-reveal': {
    from: { opacity: 0 },
    to: { opacity: 1 },
  },
  animation: `delayed-reveal ${SKELETON_FADE_MS}ms ease-out ${SKELETON_DELAY_MS}ms forwards`,
  // The hold is timing rather than motion, so keep it under reduced motion
  // and collapse only the fade.
  '@media (prefers-reduced-motion: reduce)': {
    animationDuration: '1ms',
  },
};

export interface DelayedRevealProps {
  children: React.ReactNode;
  sx?: SxProps<Theme>;
}

/**
 * Wraps a loading fallback so it stays invisible for `SKELETON_DELAY_MS`, and
 * announces it as a full-width status region.
 *
 * Every page skeleton roots itself here, so the delay and the accessibility
 * attributes are declared once. `delayedRevealSx` is exported separately for a
 * fallback that needs to apply the hold to its own container.
 */
export default function DelayedReveal({ children, sx }: DelayedRevealProps) {
  return (
    <Box
      sx={[
        { width: '100%', ...delayedRevealSx },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      role="status"
      aria-label="Loading page"
    >
      {children}
    </Box>
  );
}
