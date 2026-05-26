import { forwardRef } from 'react';
import SvgIcon, { type SvgIconProps } from '@mui/material/SvgIcon';
import { getNavIconViewport } from './navIconViewport';

// Material Symbols "kid_star" — Figma Frontend node 841:38436
const KID_STAR_ICON_PATH =
  'M5.625 4.4L8.425 0.775C8.625 0.508333 8.8625 0.3125 9.1375 0.1875C9.4125 0.0625 9.7 0 10 0C10.3 0 10.5875 0.0625 10.8625 0.1875C11.1375 0.3125 11.375 0.508333 11.575 0.775L14.375 4.4L18.625 5.825C19.0583 5.95833 19.4 6.20417 19.65 6.5625C19.9 6.92083 20.025 7.31667 20.025 7.75C20.025 7.95 19.9958 8.15 19.9375 8.35C19.8792 8.55 19.7833 8.74167 19.65 8.925L16.9 12.825L17 16.925C17.0167 17.5083 16.825 18 16.425 18.4C16.025 18.8 15.5583 19 15.025 19C14.9917 19 14.8083 18.975 14.475 18.925L10 17.675L5.525 18.925C5.44167 18.9583 5.35 18.9792 5.25 18.9875C5.15 18.9958 5.05833 19 4.975 19C4.44167 19 3.975 18.8 3.575 18.4C3.175 18 2.98333 17.5083 3 16.925L3.1 12.8L0.375 8.925C0.241667 8.74167 0.145833 8.55 0.0875 8.35C0.0291667 8.15 0 7.95 0 7.75C0 7.33333 0.120833 6.94583 0.3625 6.5875C0.604167 6.22917 0.941667 5.975 1.375 5.825L5.625 4.4ZM6.85 6.125L2 7.725L5.1 12.2L5 16.975L10 15.6L15 17L14.9 12.2L18 7.775L13.15 6.125L10 2L6.85 6.125Z';

const { viewBox, transform } = getNavIconViewport(20.025, 19);

const KidStarIcon = forwardRef<SVGSVGElement, SvgIconProps>(
  function KidStarIcon(props, ref) {
    return (
      <SvgIcon ref={ref} viewBox={viewBox} {...props}>
        <path
          d={KID_STAR_ICON_PATH}
          fill="currentColor"
          transform={transform}
        />
      </SvgIcon>
    );
  }
);

export default KidStarIcon;
