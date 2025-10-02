'use client';

import React from 'react';
import Box from '@mui/material/Box';
import { Breadcrumbs, Typography } from '@mui/material';
import Link from 'next/link';
import NavigateNextIcon from '@mui/icons-material/NavigateNext';
import NewTestGrid from './components/NewTestsGrid';
import { useRouter } from 'next/navigation';

export default function NewTestPage() {
  const router = useRouter();

  const handleSave = () => {
    router.push('/tests');
  };

  const handleCancel = () => {
    router.push('/tests');
  };

  return (
    <Box sx={{ flexGrow: 1, p: 3 }}>
      {/* Breadcrumbs */}
      <Breadcrumbs
        separator={<NavigateNextIcon fontSize="small" />}
        aria-label="breadcrumb"
        sx={{ mb: 3 }}
      >
        <Link
          href="/tests"
          passHref
          style={{ textDecoration: 'none', color: 'inherit' }}
        >
          <Typography color="text.primary">Tests</Typography>
        </Link>
        <Typography color="text.primary">New Test</Typography>
      </Breadcrumbs>

      <NewTestGrid onSave={handleSave} onCancel={handleCancel} />
    </Box>
  );
}
