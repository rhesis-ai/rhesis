'use client';

import * as React from 'react';
import { Box, Paper, Typography, Button } from '@mui/material';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface SuccessStepProps {
  projectId?: string;
}

export default function SuccessStep({ projectId }: SuccessStepProps) {
  const router = useRouter();

  return (
    <Box sx={{ textAlign: 'center' }}>
      <Paper sx={{ p: 4, mb: 3 }}>
        <CheckCircleOutlineIcon
          sx={{ fontSize: 64, color: 'success.main', mb: 2 }}
        />
        <Typography variant="h5" gutterBottom>
          Project Created Successfully!
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Your project has been created and is ready to use. You can now start configuring your test sets and running evaluations.
        </Typography>
        {projectId && (
          <Typography variant="body2" sx={{ mb: 2 }}>
            View your project at:{' '}
            <Link 
              href={`/projects-legacy/${projectId}`}
              style={{ color: 'primary.main', textDecoration: 'underline' }}
            >
              /projects-legacy/{projectId}
            </Link>
          </Typography>
        )}
        <Box sx={{ mt: 4 }}>
          <Button
            variant="contained"
            onClick={() => projectId && router.push(`/projects-legacy/${projectId}`)}
            sx={{ mr: 2 }}
            disabled={!projectId}
          >
            View Project
          </Button>
          <Button
            variant="outlined"
            onClick={() => router.push('/projects-legacy')}
            sx={{ mr: 2 }}
          >
            Go to Projects
          </Button>
        </Box>
      </Paper>
    </Box>
  );
} 