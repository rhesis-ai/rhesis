'use client';

import { useEffect, useState } from 'react';
import {
  Box,
  CircularProgress,
  Typography,
  Paper,
  Button,
  useTheme,
  Fade,
  Grow,
} from '@mui/material';
import WarningAmberIcon from '@mui/icons-material/WarningAmber';
import Image from 'next/image';
import { getClientApiBaseUrl } from '@/utils/url-resolver';

export default function DemoPage() {
  const [showCredentials, setShowCredentials] = useState(false);
  const [isRedirecting, setIsRedirecting] = useState(false);
  const [showBackground, setShowBackground] = useState(false);
  const theme = useTheme();

  useEffect(() => {
    // Show credentials after a brief moment
    const timer = setTimeout(() => {
      setShowCredentials(true);
    }, 800);

    // Show background element
    const backgroundTimer = setTimeout(() => {
      setShowBackground(true);
    }, 500);

    return () => {
      clearTimeout(timer);
      clearTimeout(backgroundTimer);
    };
  }, []);

  const handleContinue = () => {
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
        bgcolor: 'background.light1',
        p: { xs: 2, sm: 3 },
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background wave element on the right side */}
      <Fade in={showBackground} timeout={1500}>
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            right: 0,
            width: '75%',
            height: '100%',
            zIndex: 0,
            opacity: 0.3,
          }}
        >
          <Image
            src="/elements/rhesis-brand-element-18.svg"
            alt="Background element"
            fill
            style={{
              objectFit: 'cover',
              objectPosition: 'left center',
            }}
          />
        </Box>
      </Fade>

      <Grow in={true} timeout={1200}>
        <Paper
          elevation={6}
          sx={{
            p: { xs: 4, sm: 6 },
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: { xs: 3, sm: 4 },
            maxWidth: 520,
            width: '100%',
            textAlign: 'center',
            borderRadius: theme.shape.borderRadius,
            bgcolor: 'background.paper',
            border: `1px solid ${theme.palette.divider}`,
            position: 'relative',
            zIndex: 1,
          }}
        >
          {/* Normal logo presentation */}
          <Box sx={{ mb: 1 }}>
            <Image
              src="/logos/rhesis-logo-platypus.png"
              alt="Rhesis AI Platypus Logo"
              width={300}
              height={150}
              style={{
                objectFit: 'contain',
              }}
            />
          </Box>

          {!showCredentials && (
            <Fade in={true} timeout={1500}>
              <Box
                sx={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  gap: 2,
                }}
              >
                <CircularProgress size={48} sx={{ color: 'primary.main' }} />
                <Typography variant="body1" color="textSecondary">
                  Preparing your demo experience...
                </Typography>
              </Box>
            </Fade>
          )}

          <Fade in={showCredentials && !isRedirecting} timeout={1000}>
            <Box
              sx={{
                textAlign: 'center',
                width: '100%',
                display: showCredentials && !isRedirecting ? 'block' : 'none',
              }}
            >
              <Typography
                variant="body1"
                color="textSecondary"
                gutterBottom
                sx={{ mb: 3 }}
              >
                Ready to explore? Here are your demo credentials:
              </Typography>

              <Paper
                elevation={2}
                sx={{
                  p: 4,
                  mt: 2,
                  bgcolor: 'background.paper',
                  border: `1px solid ${theme.palette.divider}`,
                  borderRadius: theme.shape.borderRadius,
                }}
              >
                <Typography
                  variant="h6"
                  sx={{ fontWeight: 'bold', mb: 2, color: 'text.primary' }}
                >
                  Demo login credentials
                </Typography>
                <Box
                  sx={{
                    bgcolor: 'background.paper',
                    p: 3,
                    borderRadius: theme.shape.borderRadius * 0.5,
                    border: `1px solid ${theme.palette.divider}`,
                  }}
                >
                  <Typography
                    variant="body1"
                    sx={{ fontFamily: 'monospace', lineHeight: 1.8 }}
                  >
                    <strong>Email:</strong> demo@rhesis.ai
                    <br />
                    <strong>Password:</strong> PlatypusDemo!
                  </Typography>
                </Box>
              </Paper>

              <Typography
                variant="body2"
                sx={{
                  mt: 4,
                  mb: 4,
                  p: 2,
                  bgcolor: 'background.light2',
                  color: 'text.primary',
                  borderRadius: theme.shape.borderRadius * 0.5,
                  border: `1px solid ${theme.palette.divider}`,
                  fontWeight: 'medium',
                }}
              >
                <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                  <WarningAmberIcon
                    sx={{ color: 'warning.main', mt: 0.2, flexShrink: 0 }}
                  />
                  <span>
                    Demo Account Notice: Please do not add any real or sensitive
                    data to this demo account. All data may be visible to other
                    users and will be regularly reset.
                  </span>
                </Box>
              </Typography>

              <Button
                variant="contained"
                size="large"
                onClick={handleContinue}
                sx={{
                  minWidth: 220,
                  py: 1.5,
                  px: 3,
                }}
              >
                Continue to Demo Login
              </Button>
            </Box>
          </Fade>

          <Fade in={isRedirecting} timeout={500}>
            <Box
              sx={{
                display: isRedirecting ? 'flex' : 'none',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 2,
              }}
            >
              <CircularProgress size={48} sx={{ color: 'primary.main' }} />
              <Typography variant="body1" color="textSecondary">
                Redirecting to secure login...
              </Typography>
            </Box>
          </Fade>
        </Paper>
      </Grow>
    </Box>
  );
}
