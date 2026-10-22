import React from 'react';
import { Box } from '@mui/material';

interface DetailTabPanelProps {
  children?: React.ReactNode;
  /** The tab index this panel belongs to. */
  index: number;
  /** The currently active tab index. */
  value: number;
  /** Prefix used to generate stable ARIA ids (e.g. "requirement-detail"). */
  prefix?: string;
  /** Keep children mounted while hidden, so their local state survives a tab switch. */
  keepMounted?: boolean;
}

/**
 * Accessible tab panel for entity detail pages.
 * Renders children only when `value === index` (or always, with `keepMounted`)
 * and sets correct ARIA attributes.
 */
export function DetailTabPanel({
  children,
  value,
  index,
  prefix = 'detail',
  keepMounted = false,
}: DetailTabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`${prefix}-tabpanel-${index}`}
      aria-labelledby={`${prefix}-tab-${index}`}
    >
      {(keepMounted || value === index) && <Box sx={{ pt: 5 }}>{children}</Box>}
    </div>
  );
}

export default DetailTabPanel;
