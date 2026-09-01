'use client';

import SvgIcon, { type SvgIconProps } from '@mui/material/SvgIcon';

/**
 * A crown, filled and outlined.
 *
 * Hand-drawn because there isn't one to import: `@mui/icons-material` has no
 * crown glyph, and the repo's only other icon package
 * (`@icons-pack/react-simple-icons`) is brand logos. The nearest Material icon,
 * `WorkspacePremium`, is a rosette medal -- close enough to pass a code review
 * and obviously not a crown on screen.
 *
 * One shape, two renderings, so the filled and outlined states cannot drift
 * into different silhouettes: `CrownFilledIcon` paints it, `CrownOutlinedIcon`
 * strokes it. Stroke width is 1.6 to match the weight of the Material outlined
 * icons it sits beside in the sidebar card.
 *
 * Both inherit `currentColor` and MUI's 24px `fontSize`, so the caller controls
 * colour and size exactly as it would for any icon from the Material set.
 */

/**
 * Crown body: two shoulders, three peaks, and a base band.
 *
 * Ink spans y 4.5 to 19.5, so it is centred on the 24px box's midpoint (12).
 * That matters because the icon is drawn beside a shorter pill and centred
 * against it: artwork sitting low in its own viewBox reads as a misaligned
 * icon no amount of `alignItems: center` can fix. The first version ran
 * 4.5 to 21 (centre 12.75) with a 1.5-unit gap under the body, which made the
 * base look like a detached underline and pulled the glyph visually lower
 * still. The band now sits 1 unit under the body, close enough to read as part
 * of the crown.
 *
 * Horizontally the shoulders are at x 2.5 and 21.5, centred on 12 as well.
 */
const CROWN_PATH = 'M4.5 16 L2.5 6 L8 9.5 L12 4.5 L16 9.5 L21.5 6 L19.5 16 Z';
const CROWN_BASE = 'M5 17 H19 V19.5 H5 Z';

export function CrownFilledIcon(props: SvgIconProps) {
  return (
    // `data-testid` before the spread, so a caller can still override it --
    // MUI's generated icons carry one, and tests distinguish the two states by
    // it rather than by inspecting path geometry.
    <SvgIcon viewBox="0 0 24 24" data-testid="CrownFilledIcon" {...props}>
      <path d={CROWN_PATH} />
      <path d={CROWN_BASE} />
    </SvgIcon>
  );
}

export function CrownOutlinedIcon(props: SvgIconProps) {
  return (
    <SvgIcon viewBox="0 0 24 24" data-testid="CrownOutlinedIcon" {...props}>
      <g
        fill="none"
        stroke="currentColor"
        strokeWidth={1.6}
        strokeLinejoin="round"
        strokeLinecap="round"
      >
        <path d={CROWN_PATH} />
        {/* Stroked at 1.6, so this spans ~17.5-19.1: the same band the filled
            variant paints, keeping both silhouettes centred alike. */}
        <path d="M5 18.3 H19" />
      </g>
    </SvgIcon>
  );
}
