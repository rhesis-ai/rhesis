'use client';

import {
  SkeletonSlot,
  useSkeletonMode,
} from '@/components/loading/SkeletonMode';

/**
 * Sample text a placeholder takes its width from. The font comes from the
 * real component around it, so only the length is a guess.
 */
export const PLACEHOLDER_TEXT = {
  title: 'Placeholder for the record name',
  crumb: 'Placeholder name',
  value: 'Placeholder value text',
  long: 'Placeholder for a longer description of this record',
  person: 'Firstname Lastname',
  date: '00/00/0000',
  count: '00',
} as const;

/**
 * In skeleton mode, a text-shaped placeholder as wide as `children` in the
 * surrounding font; outside it, the bare text, so a component can route its
 * value through here and render exactly as before.
 */
export function TextPlaceholder({ children }: { children?: string }) {
  const skeleton = useSkeletonMode();
  if (!skeleton) return children ?? null;
  // No text means a generic value; blank text (a figure not known yet) a short one.
  const text =
    children === undefined
      ? PLACEHOLDER_TEXT.value
      : children.trim()
        ? children
        : PLACEHOLDER_TEXT.count;
  return (
    // Inline, so it sits in a line of text like the words it stands for.
    // Top-aligned: on the baseline it would add the space below the letters,
    // making the line taller than the text it stands for.
    <SkeletonSlot
      variant="text"
      sx={{ display: 'inline-block', verticalAlign: 'top' }}
    >
      <span>{text}</span>
    </SkeletonSlot>
  );
}

/** Handler for the real controls a loading view draws inert. */
export function noop() {}
