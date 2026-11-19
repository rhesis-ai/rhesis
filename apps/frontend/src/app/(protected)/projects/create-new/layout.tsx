import * as React from 'react';
import { Box } from '@mui/material';
import { Metadata } from 'next';
import DocumentTitle from '@/components/common/DocumentTitle';

export const metadata: Metadata = {
  title: 'Create New Project',
};

export default function CreateProjectLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'flex-start',
        padding: 3,
      }}
    >
      <DocumentTitle title="Create New Project" />
      {children}
    </Box>
  );
}
