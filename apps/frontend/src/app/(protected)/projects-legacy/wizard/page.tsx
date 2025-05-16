import * as React from 'react';
import { Box, Stepper, Step, StepLabel, Paper, Typography, Breadcrumbs } from '@mui/material';
import Link from 'next/link';
import { auth } from '@/auth';
import NewProjectForm from './components/NewProjectForm';

const steps = [
  'Repository',
  'Requirements',
  'Scenarios',
  'Personas',
  'Complete'
];

export default async function NewProjectPage() {
  try {
    const session = await auth();
    
    if (!session?.session_token) {
      throw new Error('No session token available');
    }
    
    return (
      <Box sx={{ p: 3 }}>
        <NewProjectForm sessionToken={session.session_token} />
      </Box>
    );
  } catch (error) {
    const errorMessage = (error as Error).message;
    return (
      <Box sx={{ p: 3 }}>
        <Typography color="error">
          Error creating project: {errorMessage}
        </Typography>
      </Box>
    );
  }
} 