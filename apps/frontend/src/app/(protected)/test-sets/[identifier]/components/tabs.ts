// Kept apart from TestSetDetailTabs so the route's loading view can draw the
// same tabs without pulling the page in.

import type { ComponentType } from 'react';
import type { SvgIconProps } from '@mui/material/SvgIcon';
import LinkIcon from '@mui/icons-material/Link';
import TestRunsIcon from '@/components/TestRunsIcon';

export const TAB_KEYS = ['basic', 'linked', 'runs', 'tasks'] as const;
export type TestSetTabKey = (typeof TAB_KEYS)[number];

export const TAB_LABELS: Record<TestSetTabKey, string> = {
  basic: 'Basic Information',
  linked: 'Tests',
  runs: 'Test Runs',
  tasks: 'Tasks',
};

/** Icons drawn before a tab's label. */
export const TAB_ICONS: Partial<
  Record<TestSetTabKey, ComponentType<SvgIconProps>>
> = {
  linked: LinkIcon,
  runs: TestRunsIcon,
};
