'use client';

import {
  Box,
  Grid,
  Paper,
  AppBar,
  Toolbar,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material';
import Image from 'next/image';
import LoginSection from '@/components/auth/LoginSection';
import CheckCircleIcon from '@mui/icons-material/CheckCircleOutlined';
import GroupAddIcon from '@mui/icons-material/GroupAddOutlined';
import ControlCameraIcon from '@mui/icons-material/ControlCameraOutlined';
import TuneIcon from '@mui/icons-material/TuneOutlined';

export default function RegisterPage() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));

  return (
    <Grid container component="main" sx={{ height: '100vh' }}>
      {/* Left side - Branding */}
      <Grid
        sx={{
          backgroundColor: 'primary.dark',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
        }}
        size={{ xs: false, sm: 4, md: 7 }}
      >
        <AppBar
          position="relative"
          color="transparent"
          elevation={0}
          sx={{ background: 'transparent', boxShadow: 'none' }}
        >
          <Toolbar>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Image
                src="/logos/rhesis-logo-platypus.png"
                alt="Rhesis AI Logo"
                width={200}
                height={0}
                style={{ height: 'auto' }}
                priority
              />
            </Box>
          </Toolbar>
        </AppBar>
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
          <Box sx={{ mt: 4, display: 'flex', flexDirection: 'column', gap: 3 }}>
            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <CheckCircleIcon sx={{ color: 'common.white' }} /> Your
                expertise, in every test.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                Transform business knowledge and expert input directly into
                powerful, actionable test cases.
              </Typography>
            </Box>
            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <GroupAddIcon sx={{ color: 'common.white' }} /> Collaboration
                built in.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                Bring subject matter experts into the loop — seamlessly
                contribute, review, and refine tests together.
              </Typography>
            </Box>
            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <ControlCameraIcon sx={{ color: 'common.white' }} /> End-to-end
                control.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                From test generation to execution to results, manage the entire
                validation process in one place.
              </Typography>
            </Box>
            <Box>
              <Typography
                variant="h6"
                color="common.white"
                fontWeight="bold"
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}
              >
                <TuneIcon sx={{ color: 'common.white' }} /> Scale your
                validation power.
              </Typography>
              <Typography
                variant="body2"
                color="common.white"
                sx={{ maxWidth: '90%', opacity: 0.95, ml: 4 }}
              >
                Automate, adapt, and expand test coverage effortlessly — no
                matter how fast your use cases evolve.
              </Typography>
            </Box>
          </Box>
        </Box>
      </Grid>
      {/* Right side - Registration form */}
      <Grid
        component={Paper}
        elevation={6}
        square
        size={{ xs: 12, sm: 8, md: 5 }}
      >
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
          {isMobile && (
            <Box sx={{ mb: 4 }}>
              <Image
                src="/logos/rhesis-logo-platypus.png"
                alt="Rhesis AI Logo"
                width={160}
                height={0}
                style={{ height: 'auto' }}
                priority
              />
            </Box>
          )}
          <Box sx={{ width: '100%', maxWidth: 400 }}>
            <LoginSection isRegistration />
          </Box>
        </Box>
      </Grid>
    </Grid>
  );
}
