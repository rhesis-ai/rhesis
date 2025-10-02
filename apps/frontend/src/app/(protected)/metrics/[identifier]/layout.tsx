'use client';

import { Box } from '@mui/material';

export default function MetricLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Box sx={{ p: 3, height: '100%' }}>{children}</Box>;
}
