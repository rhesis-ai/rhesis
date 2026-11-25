'use client';

import React, { createContext, useContext } from 'react';
import Skeleton from '@mui/material/Skeleton';
import type { SxProps, Theme } from '@mui/material/styles';
import { delayedRevealSx } from './DelayedReveal';

/**
 * A page rendered inside `SkeletonMode` is its own loading view: the route's
 * `loading.tsx` renders the page component itself, and the components that
 * depend on data or on the user's input draw a placeholder of their own size
 * in place of themselves. Text the page already knows (title, description,
 * breadcrumbs, tab labels' positions) stays real. Every size comes from the
 * real component, so a placeholder can't drift from what replaces it.
 */
const SkeletonModeContext = createContext(false);

export function SkeletonMode({ children }: { children: React.ReactNode }) {
  return (
    <SkeletonModeContext.Provider value>
      {children}
    </SkeletonModeContext.Provider>
  );
}

/** True while rendering a route's loading view. */
export function useSkeletonMode(): boolean {
  return useContext(SkeletonModeContext);
}

export interface SkeletonSlotProps {
  children: React.ReactElement;
  /** `circular` for round controls (FABs), `rounded` for the rest. */
  variant?: 'rounded' | 'circular' | 'text';
  sx?: SxProps<Theme>;
}

/**
 * In skeleton mode, a placeholder exactly the size of `children` (MUI Skeleton
 * infers its size from them and hides them, so they can't be seen, clicked or
 * focused); otherwise `children` as they are.
 */
export function SkeletonSlot({
  children,
  variant = 'rounded',
  sx,
}: SkeletonSlotProps) {
  if (!useSkeletonMode()) return children;
  return (
    <Skeleton
      variant={variant}
      sx={[
        { maxWidth: 'none', flexShrink: 0, ...delayedRevealSx },
        ...(Array.isArray(sx) ? sx : sx ? [sx] : []),
      ]}
      aria-hidden
    >
      {children}
    </Skeleton>
  );
}
