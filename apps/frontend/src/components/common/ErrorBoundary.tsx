'use client';

import React, { useState, useCallback } from 'react';
import { Box, Typography, Button, Paper, Alert } from '@mui/material';
import { useTheme } from '@mui/material/styles';
import RefreshIcon from '@mui/icons-material/Refresh';

interface ErrorBoundaryProps {
  children: React.ReactNode;
  fallback?: React.ComponentType<{ error?: Error; retry: () => void }>;
}

interface ErrorInfo {
  componentStack?: string;
}

export function ErrorBoundary({ children, fallback }: ErrorBoundaryProps) {
  const theme = useTheme();
  const [error, setError] = useState<Error | null>(null);
  const [errorInfo, setErrorInfo] = useState<ErrorInfo | null>(null);

  const handleError = useCallback((error: Error, errorInfo?: ErrorInfo) => {
    console.error('🚨 [ERROR BOUNDARY] Component crashed:', {
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack,
      },
      errorInfo: {
        componentStack: errorInfo?.componentStack,
      },
      timestamp: new Date().toISOString(),
      userAgent: typeof window !== 'undefined' ? window.navigator.userAgent : 'unknown',
      url: typeof window !== 'undefined' ? window.location.href : 'unknown',
    });

    setError(error);
    setErrorInfo(errorInfo || null);
  }, []);

  const handleRetry = useCallback(() => {
    console.log('🔄 [ERROR BOUNDARY] Retrying...');
    setError(null);
    setErrorInfo(null);
  }, []);

  // If there's an error, render the fallback UI
  if (error) {
    if (fallback) {
      const FallbackComponent = fallback;
      return <FallbackComponent error={error} retry={handleRetry} />;
    }

    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '400px',
          p: 3,
        }}
      >
        <Paper
          elevation={3}
          sx={{
            p: 4,
            maxWidth: 600,
            width: '100%',
            textAlign: 'center',
          }}
        >
          <Alert severity="error" sx={{ mb: 3 }}>
            <Typography variant="h6" gutterBottom>
              Something went wrong
            </Typography>
            <Typography variant="body2" color="text.secondary">
              The application encountered an unexpected error. Please try refreshing the page or contact support if the problem persists.
            </Typography>
          </Alert>

          {error && (
            <Box sx={{ mb: 3, textAlign: 'left' }}>
              <Typography variant="subtitle2" gutterBottom>
                Error Details:
              </Typography>
              <Box
                component="pre"
                sx={{
                  backgroundColor: 'grey.100',
                  p: 2,
                  borderRadius: theme.shape.borderRadius,
                  fontSize: theme.typography.helperText.fontSize,
                  overflow: 'auto',
                  maxHeight: 200,
                }}
              >
                {error.message}
                {'\n\n'}
                {error.stack}
              </Box>
            </Box>
          )}

          <Box sx={{ display: 'flex', gap: 2, justifyContent: 'center' }}>
            <Button
              variant="contained"
              startIcon={<RefreshIcon />}
              onClick={handleRetry}
            >
              Try Again
            </Button>
            <Button
              variant="outlined"
              onClick={() => window.location.reload()}
            >
              Refresh Page
            </Button>
          </Box>
        </Paper>
      </Box>
    );
  }

  // Use a wrapper component to catch errors
  return (
    <ErrorCatcher onError={handleError}>
      {children}
    </ErrorCatcher>
  );
}

// Wrapper component that catches errors and calls the error handler
interface ErrorCatcherProps {
  children: React.ReactNode;
  onError: (error: Error, errorInfo?: ErrorInfo) => void;
}

class ErrorCatcher extends React.Component<ErrorCatcherProps, { hasError: boolean }> {
  constructor(props: ErrorCatcherProps) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    console.error('🚨 [ERROR BOUNDARY] Caught error:', error);
    return { hasError: true };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    this.props.onError(error, {
      componentStack: errorInfo.componentStack || undefined,
    });
  }

  render() {
    if (this.state.hasError) {
      // This will be handled by the parent ErrorBoundary
      return null;
    }

    return this.props.children;
  }
}

// Hook version for functional components
export function useErrorHandler() {
  return React.useCallback((error: Error, errorInfo?: { componentStack?: string }) => {
    console.error('🚨 [ERROR HANDLER] Manual error report:', {
      error: {
        name: error.name,
        message: error.message,
        stack: error.stack,
      },
      errorInfo,
      timestamp: new Date().toISOString(),
      url: typeof window !== 'undefined' ? window.location.href : 'unknown',
    });
  }, []);
}

export default ErrorBoundary;
