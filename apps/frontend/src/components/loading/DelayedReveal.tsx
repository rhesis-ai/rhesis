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
 * `nextjs-toploader` covers the window: the progress bar starts on click, so
 * a navigation shorter than the delay still gives immediate feedback.
 *
 * Suspense unmounts the fallback as soon as the page resolves, so a page
 * that settles before the delay elapses paints nothing in between.
 *
 * 500ms sits between the ~300ms floor below which users don't perceive a
 * delay and the 1s mark where they notice one (Nielsen's response-time
 * limits), and is meant to clear a backend round trip for an empty list.
 * TanStack Router defaults the same knob (`defaultPendingMs`) to 1000ms;
 * raise this if empty pages still flash a skeleton in production.
 *
 * The complementary half of this pattern, a minimum display duration
 * (TanStack's `pendingMinMs`), is deliberately absent: React owns when it
 * unmounts a `loading.tsx` fallback, so honouring a minimum would mean
 * hand-rolled Suspense boundaries and client timers on every route. The fade
 * below softens that case instead, since a fallback unmounted mid-fade never
 * reached full opacity.
 */
export const SKELETON_DELAY_MS = 500;

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
 * Wraps a loading fallback so it stays invisible for `SKELETON_DELAY_MS`.
 * Both page skeletons apply `delayedRevealSx` themselves; use this for
 * fallbacks that don't, such as a bare `PageLoadingState`.
 */
export default function DelayedReveal({ children, sx }: DelayedRevealProps) {
  return (
    <Box
      sx={[delayedRevealSx, ...(Array.isArray(sx) ? sx : sx ? [sx] : [])]}
      role="status"
      aria-label="Loading"
    >
      {children}
    </Box>
  );
}
