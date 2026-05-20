import { forwardRef } from 'react';
import SvgIcon, { type SvgIconProps } from '@mui/material/SvgIcon';
import { getNavIconViewport } from './navIconViewport';

// Material Symbols "checklist_rtl" — Figma Frontend node 841:38425
const TASKS_ICON_PATH =
  'M14.375 15.075L10.825 11.525L12.225 10.125L14.35 12.25L18.6 8L20 9.425L14.375 15.075ZM14.375 7.075L10.825 3.525L12.225 2.125L14.35 4.25L18.6 0L20 1.425L14.375 7.075ZM0 13.075V11.075H9V13.075H0ZM0 5.075V3.075H9V5.075H0Z';

const { viewBox, transform } = getNavIconViewport(20, 15.075);

const TasksIcon = forwardRef<SVGSVGElement, SvgIconProps>(
  function TasksIcon(props, ref) {
    return (
      <SvgIcon ref={ref} viewBox={viewBox} {...props}>
        <path d={TASKS_ICON_PATH} fill="currentColor" transform={transform} />
      </SvgIcon>
    );
  }
);

export default TasksIcon;
