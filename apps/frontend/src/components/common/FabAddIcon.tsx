import { forwardRef } from 'react';
import SvgIcon, { type SvgIconProps } from '@mui/material/SvgIcon';

// Figma Frontend node 1639:10079 — Icons/Weight 400/add_2 (18×18 viewBox)
const FAB_ADD_ICON_PATH = 'M8 18V10H0V8H8V0H10V8H18V10H10V18H8Z';

const FabAddIcon = forwardRef<SVGSVGElement, SvgIconProps>(
  function FabAddIcon(props, ref) {
    return (
      <SvgIcon ref={ref} viewBox="0 0 18 18" {...props}>
        <path d={FAB_ADD_ICON_PATH} fill="currentColor" />
      </SvgIcon>
    );
  }
);

export default FabAddIcon;
