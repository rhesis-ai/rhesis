// Kept apart from TestDetailTabs so the route's loading view can draw the
// same tabs without pulling the page in.

import type { ComponentType } from 'react';
import type { SvgIconProps } from '@mui/material/SvgIcon';
import LinkIcon from '@mui/icons-material/Link';

export const TAB_KEYS = ['basic', 'linked', 'history', 'tasks'] as const;

export const TAB_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Overview',
  linked: 'Test Sets',
  history: 'Execution History',
  tasks: 'Tasks',
};

/** Icons drawn before a tab's label. */
export const TAB_ICONS: Partial<
  Record<(typeof TAB_KEYS)[number], ComponentType<SvgIconProps>>
> = {
  linked: LinkIcon,
};
