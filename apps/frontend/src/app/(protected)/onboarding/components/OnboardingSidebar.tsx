'use client';

import Image from 'next/image';
import ArrowBackIcon from '@mui/icons-material/ArrowBack';
import { Box, Typography } from '@mui/material';
import { ONBOARDING_STEPS } from './onboarding-steps';

interface OnboardingSidebarProps {
  activeStep: number;
}

export default function OnboardingSidebar({
  activeStep,
}: OnboardingSidebarProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'space-between',
        bgcolor: theme => theme.palette.greyscale.fieldSurface,
        borderRadius: '20px',
        px: 5,
        py: '50px',
        minHeight: { xs: 'auto', md: 'calc(100vh - 40px)' },
        width: { xs: '100%', md: 400 },
        flexShrink: 0,
      }}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: '60px' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Box
            sx={{ width: 40, height: 40, position: 'relative', flexShrink: 0 }}
          >
            <Image
              src="/logos/rhesis-logo-favicon.svg"
              alt="Rhesis AI"
              width={40}
              height={40}
              priority
            />
          </Box>
          <Typography
            sx={{
              fontSize: 23,
              fontWeight: 700,
              lineHeight: '27.6px',
              color: 'primary.main',
            }}
          >
            Rhesis AI
          </Typography>
        </Box>

        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: '30px',
            position: 'relative',
          }}
        >
          {ONBOARDING_STEPS.map((step, index) => {
            const isActive = index === activeStep;
            const isPast = index < activeStep;
            const Icon = step.icon;

            return (
              <Box
                key={step.id}
                sx={{
                  display: 'flex',
                  gap: '10px',
                  alignItems: 'flex-start',
                  py: '5px',
                  position: 'relative',
                }}
              >
                {index < ONBOARDING_STEPS.length - 1 && (
                  <Box
                    sx={{
                      position: 'absolute',
                      left: 12,
                      top: 34,
                      width: '1px',
                      height: index === 0 ? 70 : index === 1 ? 65 : 67,
                      bgcolor: theme =>
                        isPast || isActive
                          ? theme.palette.primary.main
                          : theme.palette.greyscale.border,
                    }}
                  />
                )}
                <Icon
                  sx={{
                    fontSize: 24,
                    color: theme =>
                      isActive
                        ? theme.palette.greyscale.title
                        : isPast
                          ? theme.palette.greyscale.subtitle
                          : theme.palette.greyscale.subtitle,
                    flexShrink: 0,
                    mt: '2px',
                  }}
                />
                <Box>
                  <Typography
                    sx={{
                      fontSize: 18,
                      fontWeight: 700,
                      lineHeight: '25px',
                      color: theme =>
                        isActive
                          ? theme.palette.greyscale.title
                          : theme.palette.greyscale.subtitle,
                    }}
                  >
                    {step.sidebarTitle}
                  </Typography>
                  <Typography
                    sx={{
                      fontSize: 14,
                      lineHeight: '22px',
                      color: theme =>
                        isActive
                          ? theme.palette.greyscale.body
                          : theme.palette.greyscale.subtitle,
                      mt: '8px',
                    }}
                  >
                    {step.sidebarSubtitle}
                  </Typography>
                </Box>
              </Box>
            );
          })}
        </Box>
      </Box>

      <Box
        component="a"
        href="https://www.rhesis.ai"
        target="_blank"
        rel="noopener noreferrer"
        sx={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '2px',
          textDecoration: 'none',
          color: 'primary.main',
          fontSize: 12,
          lineHeight: '18px',
          mt: { xs: 4, md: 0 },
          '&:hover': { textDecoration: 'underline' },
        }}
      >
        <ArrowBackIcon sx={{ fontSize: 18 }} />
        Back home
      </Box>
    </Box>
  );
}
