'use client';

import React, { Component, ReactNode } from 'react';
import { Alert, AlertTitle, Box, Button } from '@mui/material';
import { RefreshIcon } from '@/components/icons';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class TaskErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {}

  handleRetry = () => {
    this.setState({ hasError: false, error: undefined });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Box sx={{ p: 2 }}>
          <Alert
            severity="error"
            action={
              <Button
                color="inherit"
                size="small"
                onClick={this.handleRetry}
                startIcon={<RefreshIcon />}
              >
                Retry
              </Button>
            }
          >
            <AlertTitle>Something went wrong</AlertTitle>
            There was an error with the task component. Please try refreshing or
            contact support if the problem persists.
            {process.env.NODE_ENV === 'development' && this.state.error && (
              <Box sx={{ mt: 1, fontSize: '0.75rem', fontFamily: 'monospace' }}>
                {this.state.error.message}
              </Box>
            )}
          </Alert>
        </Box>
      );
    }

    return this.props.children;
  }
}
