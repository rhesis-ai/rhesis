'use client';

import * as React from 'react';
import { 
  Box, 
  Container, 
  AppBar, 
  Toolbar, 
  Typography, 
  CircularProgress,
  Paper,
  Grid,
  useMediaQuery,
  useTheme
} from '@mui/material';
import Image from 'next/image';
import { useSession, signOut } from 'next-auth/react';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import LoginSection from '../components/auth/LoginSection';
// Import Material UI icons
import SpeedIcon from '@mui/icons-material/Speed';
import SecurityIcon from '@mui/icons-material/Security';
import EmojiEmotionsIcon from '@mui/icons-material/EmojiEmotions';
import LightbulbIcon from '@mui/icons-material/Lightbulb';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import GroupAddIcon from '@mui/icons-material/GroupAdd';
import ControlCameraIcon from '@mui/icons-material/ControlCamera';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import TuneIcon from '@mui/icons-material/Tune';

export default function LandingPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const [sessionExpired, setSessionExpired] = useState(false);
  const [backendSessionValid, setBackendSessionValid] = useState<boolean | null>(null);
  
  useEffect(() => {
    // Check if user was redirected due to session expiration or forced logout
    const urlParams = new URLSearchParams(window.location.search);
    const isSessionExpired = urlParams.get('session_expired') === 'true';
    const isForcedLogout = urlParams.get('force_logout') === 'true';
    
    if (isSessionExpired || isForcedLogout) {
      setSessionExpired(true);
      setBackendSessionValid(false);
      // Clear the parameters from URL
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.delete('session_expired');
      newUrl.searchParams.delete('force_logout');
      window.history.replaceState({}, '', newUrl.toString());
      
      if (status === 'authenticated') {
        signOut({ redirect: false, callbackUrl: '/' });
      }
      return;
    }
    
    // Validate backend session immediately when user appears authenticated
    if (status === 'authenticated' && session && !sessionExpired && backendSessionValid === null) {
      const validateBackendSession = async () => {
        try {
          const response = await fetch(
            `${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/verify?session_token=${session.session_token}`,
            { headers: { Accept: 'application/json' } }
          );

          if (response.ok) {
            const data = await response.json();
            if (data.authenticated && data.user) {
              setBackendSessionValid(true);
              router.replace('/dashboard');
              return;
            }
          }

          // Backend session invalid - call backend logout to clean up, then frontend logout
          try {
            await fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/auth/logout`, {
              method: 'GET',
              headers: { 'Accept': 'application/json' },
            });
          } catch (logoutError) {
            console.warn('Backend logout failed:', logoutError);
          }

          setBackendSessionValid(false);
          setSessionExpired(true);
          signOut({ redirect: false, callbackUrl: '/' });
        } catch (error) {
          console.error('Backend session validation error:', error);
          setBackendSessionValid(false);
          setSessionExpired(true);
          signOut({ redirect: false, callbackUrl: '/' });
        }
      };

      validateBackendSession();
    }
  }, [session, status, router, sessionExpired, backendSessionValid]);

  if (status === 'loading') {
    return null;
  }

  if (status === 'authenticated' && session && !sessionExpired && backendSessionValid === true) {
    return (
      <Grid container component="main" sx={{ height: '100vh' }}>
        {/* Left side - Background image and content - same as unauthenticated view */}
        <Grid
          item
          xs={false}
          sm={4}
          md={7}
          sx={{
            background: 'linear-gradient(175deg, rgba(16,24,40,1) 0%, rgba(29,41,57,1) 49%, rgba(52,64,84,1) 80%)',
            position: 'relative',
            display: 'flex',
            flexDirection: 'column',
          }}
        >
          <AppBar 
            position="relative" 
            color="transparent" 
            elevation={0} 
            sx={{ 
              background: 'transparent',
              boxShadow: 'none',
            }}
          >
            <Toolbar>
              <Box sx={{ display: 'flex', alignItems: 'center' }}>
                <Image
                  src="/rhesis-logo-white.png"
                  alt="Rhesis Logo"
                  width={180}
                  height={0}
                  style={{ height: 'auto' }}
                  priority
                />
              </Box>
            </Toolbar>
          </AppBar>
          
          {/* Content overlay on the background - same as unauthenticated view */}
          <Box
            sx={{
              position: 'relative',
              p: { xs: 3, md: 8 },
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              flex: 1,
            }}
          >
            {/* Feature points - same as unauthenticated view */}
            <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 3 }}>
              <Box>
                <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <CheckCircleIcon sx={{ color: 'white' }} /> Your expertise, in every test.
                </Typography>
                <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                  Transform business knowledge and expert input directly into powerful, actionable test cases.
                </Typography>
              </Box>

              <Box>
                <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <GroupAddIcon sx={{ color: 'white' }} /> Collaboration built in.
                </Typography>
                <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                  Bring subject matter experts into the loop — seamlessly contribute, review, and refine tests together.
                </Typography>
              </Box>

              <Box>
                <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <ControlCameraIcon sx={{ color: 'white' }} /> End-to-end control.
                </Typography>
                <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                  From test generation to execution to results, manage the entire validation process in one place.
                </Typography>
              </Box>

              <Box>
                <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                  <TuneIcon sx={{ color: 'white' }} /> Scale your validation power.
                </Typography>
                <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                  Automate, adapt, and expand test coverage effortlessly — no matter how fast your use cases evolve.
                </Typography>
              </Box>
            </Box>
          </Box>
        </Grid>

        {/* Right side - Authentication message */}
        <Grid item xs={12} sm={8} md={5} component={Paper} elevation={6} square>
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              p: { xs: 3, sm: 6, md: 8 },
            }}
          >
            {/* Show logo on mobile or smaller devices */}
            {isMobile && (
              <Box sx={{ mb: 4 }}>
                <Image
                  src="/rhesis-logo.png"
                  alt="Rhesis Logo"
                  width={150}
                  height={0}
                  style={{ height: 'auto' }}
                  priority
                />
              </Box>
            )}

            <Box sx={{ 
              width: '100%', 
              maxWidth: 400, 
              textAlign: 'center',
              p: 3,
              borderRadius: 2,
              boxShadow: '0px 4px 20px rgba(0, 0, 0, 0.1)',
              background: 'rgba(255, 255, 255, 0.9)',
            }}>
              <Typography variant="h5" gutterBottom>
                Welcome back, {session.user?.name || 'User'}!
              </Typography>
              <Typography variant="body1" gutterBottom>
                You&apos;re already logged in. Redirecting you to the dashboard...
              </Typography>
              <CircularProgress sx={{ mt: 2 }} />
            </Box>
          </Box>
        </Grid>
      </Grid>
    );
  }

  return (
    <Grid container component="main" sx={{ height: '100vh' }}>
      {/* Left side - Background image and content */}
      <Grid
        item
        xs={false}
        sm={4}
        md={7}
        sx={{
          background: 'linear-gradient(175deg, rgba(16,24,40,1) 0%, rgba(29,41,57,1) 49%, rgba(52,64,84,1) 80%)',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <AppBar 
          position="relative" 
          color="transparent" 
          elevation={0} 
          sx={{ 
            background: 'transparent',
            boxShadow: 'none',
          }}
        >
          <Toolbar>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Image
                src="/rhesis-logo-white.png"
                alt="Rhesis Logo"
                width={180}
                height={0}
                style={{ height: 'auto' }}
                priority
              />
            </Box>
          </Toolbar>
        </AppBar>
        
        {/* Content overlay on the background */}
        <Box
          sx={{
            position: 'relative',
            p: { xs: 3, md: 8 },
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'center',
            flex: 1,
          }}
        >

          {/* Feature points */}
          <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Box>
              <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <CheckCircleIcon sx={{ color: 'white' }} /> Your expertise, in every test.
              </Typography>
              <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                Transform business knowledge and expert input directly into powerful, actionable test cases.
              </Typography>
            </Box>

            <Box>
              <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <GroupAddIcon sx={{ color: 'white' }} /> Collaboration built in.
              </Typography>
              <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                Bring subject matter experts into the loop — seamlessly contribute, review, and refine tests together.
              </Typography>
            </Box>

            <Box>
              <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <ControlCameraIcon sx={{ color: 'white' }} /> End-to-end control.
              </Typography>
              <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                From test generation to execution to results, manage the entire validation process in one place.
              </Typography>
            </Box>

            <Box>
              <Typography variant="h6" color="white" fontWeight="bold" sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                <TuneIcon sx={{ color: 'white' }} /> Scale your validation power.
              </Typography>
              <Typography variant="body2" color="white" sx={{ maxWidth: '90%', opacity: 0.9, ml: 4 }}>
                Automate, adapt, and expand test coverage effortlessly — no matter how fast your use cases evolve.
              </Typography>
            </Box>
          </Box>
        </Box>
      </Grid>

      {/* Right side - Login form */}
      <Grid item xs={12} sm={8} md={5} component={Paper} elevation={6} square>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            height: '100%',
            p: { xs: 3, sm: 6, md: 8 },
          }}
        >
          {/* Show logo on mobile or smaller devices */}
          {isMobile && (
            <Box sx={{ mb: 4 }}>
              <Image
                src="/rhesis-logo.png"
                alt="Rhesis Logo"
                width={150}
                height={0}
                style={{ height: 'auto' }}
                priority
              />
            </Box>
          )}

          <Box sx={{ width: '100%', maxWidth: 400 }}>
            <LoginSection />
          </Box>
        </Box>
      </Grid>
    </Grid>
  );
} 