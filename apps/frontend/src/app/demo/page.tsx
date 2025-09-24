'use client';

import { useEffect, useState } from 'react';
import { Box, CircularProgress, Typography, Paper, Button } from '@mui/material';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

export default function DemoPage() {
  const [showCredentials, setShowCredentials] = useState(false);
  const [isRedirecting, setIsRedirecting] = useState(false);

  useEffect(() => {
    // Show credentials after a brief moment
    const timer = setTimeout(() => {
      setShowCredentials(true);
    }, 500);
    
    return () => clearTimeout(timer);
  }, []);

  const handleContinue = () => {
    console.log('🟢 [DEBUG] Demo page - redirecting to Auth0 with demo user pre-filled');
    setIsRedirecting(true);
    
    // Redirect to backend demo endpoint which will redirect to Auth0 with login_hint
    window.location.href = `${getClientApiBaseUrl()}/auth/demo`;
  };

  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        bgcolor: 'background.default',
        p: 3,
      }}
    >
      <Paper
        elevation={3}
        sx={{
          p: 4,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: 3,
          maxWidth: 500,
          textAlign: 'center',
        }}
      >
        <Typography variant="h4" component="h1" gutterBottom>
          🐾 Rhesis Demo
        </Typography>
        
        {!showCredentials && (
          <>
            <CircularProgress size={48} />
            <Typography variant="body1" color="textSecondary">
              Preparing your demo experience...
            </Typography>
          </>
        )}

        {showCredentials && !isRedirecting && (
          <Box sx={{ textAlign: 'center', width: '100%' }}>
            <Typography variant="body1" color="textSecondary" gutterBottom>
              Ready to try Rhesis? Here are your demo credentials:
            </Typography>
            
            <Paper 
              elevation={2} 
              sx={{ 
                p: 3, 
                mt: 2, 
                bgcolor: 'primary.50',
                border: '2px solid',
                borderColor: 'primary.main'
              }}
            >
              <Typography variant="h6" color="primary" sx={{ fontWeight: 'bold', mb: 2 }}>
                Demo Login Credentials
              </Typography>
              <Typography variant="body1" sx={{ fontFamily: 'monospace', lineHeight: 1.8 }}>
                <strong>Email:</strong> demo@rhesis.ai<br/>
                <strong>Password:</strong> tryrhesis
              </Typography>
            </Paper>
            
            <Typography variant="body2" color="textSecondary" sx={{ mt: 2, mb: 3 }}>
              Click below to proceed to the secure login page. The email will be pre-filled!
            </Typography>

            <Button 
              variant="contained" 
              size="large" 
              onClick={handleContinue}
              sx={{ minWidth: 200 }}
            >
              Continue to Demo Login
            </Button>
          </Box>
        )}

        {isRedirecting && (
          <>
            <CircularProgress size={48} />
            <Typography variant="body1" color="textSecondary">
              Redirecting to secure login...
            </Typography>
          </>
        )}
      </Paper>
    </Box>
  );
}
