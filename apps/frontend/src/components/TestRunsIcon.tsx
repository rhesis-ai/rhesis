import { forwardRef } from 'react';
import SvgIcon, { type SvgIconProps } from '@mui/material/SvgIcon';
import { getNavIconViewport } from './navIconViewport';

// Material Symbols "animated_images" — Figma Frontend node 841:38421
const TEST_RUNS_ICON_PATH =
  'M9.89167 11.5L15.8917 7.5L9.89167 3.5V11.5ZM10.5917 17H16.1917C16.075 17.4333 15.875 17.7833 15.5917 18.05C15.3083 18.3167 14.9417 18.4833 14.4917 18.55L3.59167 19.875C3.04167 19.9583 2.54583 19.8292 2.10417 19.4875C1.6625 19.1458 1.40833 18.7 1.34167 18.15L0.0166667 7.225C-0.05 6.675 0.0833333 6.18333 0.416667 5.75C0.75 5.31667 1.19167 5.06667 1.74167 5L2.89167 4.85V6.85L1.99167 6.975L3.34167 17.9L10.5917 17ZM6.89167 15C6.34167 15 5.87083 14.8042 5.47917 14.4125C5.0875 14.0208 4.89167 13.55 4.89167 13V2C4.89167 1.45 5.0875 0.979167 5.47917 0.5875C5.87083 0.195833 6.34167 0 6.89167 0H17.8917C18.4417 0 18.9125 0.195833 19.3042 0.5875C19.6958 0.979167 19.8917 1.45 19.8917 2V13C19.8917 13.55 19.6958 14.0208 19.3042 14.4125C18.9125 14.8042 18.4417 15 17.8917 15H6.89167ZM6.89167 13H17.8917V2H6.89167V13Z';

const { viewBox, transform } = getNavIconViewport(19.8917, 19.8995);

const TestRunsIcon = forwardRef<SVGSVGElement, SvgIconProps>(
  function TestRunsIcon(props, ref) {
    return (
      <SvgIcon ref={ref} viewBox={viewBox} {...props}>
        <path
          d={TEST_RUNS_ICON_PATH}
          fill="currentColor"
          transform={transform}
        />
      </SvgIcon>
    );
  }
);

export default TestRunsIcon;
