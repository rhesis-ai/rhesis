import React from 'react';
import { Box } from '@mui/material';

interface DetailTabPanelProps {
  children?: React.ReactNode;
  /** The tab index this panel belongs to. */
  index: number;
  /** The currently active tab index. */
  value: number;
  /** Prefix used to generate stable ARIA ids (e.g. "behavior-detail"). */
  prefix?: string;
}

/**
 * Accessible tab panel for entity detail pages.
 * Renders children only when `value === index` and sets correct ARIA attributes.
 */
export function DetailTabPanel({
  children,
  value,
  index,
  prefix = 'detail',
}: DetailTabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`${prefix}-tabpanel-${index}`}
      aria-labelledby={`${prefix}-tab-${index}`}
    >
      {value === index && <Box sx={{ pt: 5 }}>{children}</Box>}
    </div>
  );
}

export default DetailTabPanel;
