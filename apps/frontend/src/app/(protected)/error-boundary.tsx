'use client';

import * as React from 'react';
import { Box, Button, Typography, Paper } from '@mui/material';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

class ErrorBoundary extends React.Component<
  {
    children: React.ReactNode;
  },
  {
    hasError: boolean;
  }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    // Only set error state for authentication errors
    if (
      error.message.includes('auth') ||
      error.message.includes('session') ||
      error.message.includes('unauthorized')
    ) {
      return { hasError: true };
    }
    // Ignore other errors
    return null;
  }

  render() {
    if (this.state.hasError) {
      return <AuthErrorFallback />;
    }
    return this.props.children;
  }
}

function AuthErrorFallback() {
  const router = useRouter();

  useEffect(() => {
    const timer = setTimeout(() => {
      router.push('/');
    }, 3000);

    return () => clearTimeout(timer);
  }, [router]);

  return (
    <Box sx={{ p: 3 }}>
      <Paper sx={{ p: 3, textAlign: 'center' }}>
        <Typography variant="h6" gutterBottom>
          Your session has expired
        </Typography>
        <Typography variant="body1" sx={{ mb: 3 }}>
          Please sign in again to continue. Redirecting to login page...
        </Typography>
        <Button variant="contained" onClick={() => router.push('/')}>
          Sign In Now
        </Button>
      </Paper>
    </Box>
  );
}

export default function AuthErrorBoundary({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ErrorBoundary>{children}</ErrorBoundary>;
}
