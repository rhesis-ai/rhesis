'use client';

import { alpha, Box, Button, Typography } from '@mui/material';
import ArrowBackIcon from '@mui/icons-material/ArrowBackOutlined';
import HomeOutlinedIcon from '@mui/icons-material/HomeOutlined';
import TravelExploreOutlinedIcon from '@mui/icons-material/TravelExploreOutlined';
import Link from 'next/link';

/**
 * Root not-found page — shown when no route matches the URL at all.
 * Wrapped by app/layout.tsx so it renders inside the full app shell.
 * The URL is not interpreted because it can be arbitrary garbage.
 */
export default function RootNotFound() {
  return (
    <Box
      display="flex"
      flexDirection="column"
      alignItems="center"
      justifyContent="center"
      minHeight="80vh"
      textAlign="center"
      px={3}
    >
      <Box position="relative" mb={2}>
        <Typography
          component="span"
          sx={{
            fontSize: { xs: '6rem', sm: '9rem' },
            fontWeight: 800,
            lineHeight: 1,
            color: theme => alpha(theme.palette.text.primary, 0.07),
            userSelect: 'none',
            letterSpacing: '-0.04em',
          }}
          aria-hidden
        >
          404
        </Typography>

        <Box
          sx={{ position: 'absolute', inset: 0 }}
          display="flex"
          alignItems="center"
          justifyContent="center"
        >
          <TravelExploreOutlinedIcon
            sx={{
              fontSize: { xs: '2.5rem', sm: '3.5rem' },
              color: 'text.secondary',
            }}
          />
        </Box>
      </Box>

      <Typography variant="h5" fontWeight={600} gutterBottom>
        Page not found
      </Typography>

      <Typography
        variant="body1"
        color="text.secondary"
        sx={{ maxWidth: 400, mb: 4 }}
      >
        The URL you entered doesn&apos;t match any page in the application.
        Check for typos, or navigate back to the app.
      </Typography>

      <Box display="flex" gap={1.5} flexWrap="wrap" justifyContent="center">
        <Button
          variant="outlined"
          startIcon={<ArrowBackIcon />}
          onClick={() => window.history.back()}
        >
          Go Back
        </Button>
        <Button
          component={Link}
          href="/architect"
          variant="outlined"
          startIcon={<HomeOutlinedIcon />}
        >
          Go Home
        </Button>
      </Box>
    </Box>
  );
}
