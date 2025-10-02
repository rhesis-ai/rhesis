import * as React from 'react';
import Box from '@mui/material/Box';

export default function NewMetricLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <Box sx={{ width: '100%', py: 3 }}>{children}</Box>;
}
