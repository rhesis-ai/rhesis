'use client';

import React, { useState, useMemo, useCallback, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  IconButton,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  LinearProgress,
  Collapse,
  Badge,
  Tooltip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
  Button,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  RadioButtonUnchecked as RadioButtonUncheckedIcon,
  ExpandMore as ExpandMoreIcon,
  Close as CloseIcon,
  Lightbulb as LightbulbIcon,
} from '@mui/icons-material';
import { useRouter, usePathname, useSearchParams } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { OnboardingStep } from '@/types/onboarding';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ONBOARDING_STEPS,
  ONBOARDING_COLLAPSE_PATH,
} from '@/config/onboarding-tours';

export default function OnboardingChecklist() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { data: session } = useSession();
  const { progress, isComplete, completionPercentage, dismissOnboarding } =
    useOnboarding();

  const [expanded, setExpanded] = useState(true);
  const [confirmDialogOpen, setConfirmDialogOpen] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Handle client-side mounting to avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);

  // Auto-collapse on dashboard page or when in an onboarding tour (avoid hydration issues)
  useEffect(() => {
    const isInTour = searchParams.get('tour') !== null;
    const shouldCollapse = pathname === ONBOARDING_COLLAPSE_PATH || isInTour;
    setExpanded(!shouldCollapse);
  }, [pathname, searchParams]);

  // Memoize computed values for performance
  const incompletedSteps = useMemo(
    () => ONBOARDING_STEPS.filter(step => !progress[step.id]).length,
    [progress]
  );

  // Define all callbacks before any early returns (Rules of Hooks)
  const handleStepClick = useCallback(
    async (step: OnboardingStep) => {
      try {
        // Minimize the box when starting a task
        setExpanded(false);

        // For steps that require projects (like endpoint setup),
        // fetch the first project and navigate to its detail page
        if (step.requiresProjects && session?.session_token) {
          try {
            const apiFactory = new ApiClientFactory(session.session_token);
            const projectsClient = apiFactory.getProjectsClient();
            const response = await projectsClient.getProjects();
            const projects = Array.isArray(response)
              ? response
              : response?.data || [];

            if (projects.length > 0) {
              // Navigate to the first project's detail page
              router.push(`/projects/${projects[0].id}?tour=${step.tourId}`);
              return;
            }
          } catch (error) {
            console.error('Error fetching projects for onboarding:', error);
            // Fall through to default navigation
          }
        }

        router.push(step.targetPath);
      } catch (error) {
        console.error('Failed to navigate to onboarding step:', error);
      }
    },
    [router, session]
  );

  const handleToggleExpanded = useCallback(() => {
    setExpanded(prev => !prev);
  }, []);

  const handleDismissClick = useCallback(() => {
    setConfirmDialogOpen(true);
  }, []);

  const handleConfirmDismiss = useCallback(() => {
    dismissOnboarding();
    setConfirmDialogOpen(false);
  }, [dismissOnboarding]);

  const handleCancelDismiss = useCallback(() => {
    setConfirmDialogOpen(false);
  }, []);

  // Don't render until mounted (avoid hydration mismatch)
  // Don't show if dismissed or completed
  if (!mounted || progress.dismissed || isComplete) {
    return null;
  }

  return (
    <>
      <Box
        sx={{
          position: 'fixed',
          bottom: 16,
          right: 16,
          zIndex: 1300,
          maxWidth: 380,
          width: '100%',
        }}
        role="complementary"
        aria-label="Onboarding checklist"
      >
        <Card
          elevation={8}
          sx={{
            borderRadius: theme => theme.shape.borderRadius / 2,
            overflow: 'hidden',
            border: '2px solid',
            borderColor: 'primary.main',
          }}
        >
          {/* Header */}
          <Box
            sx={{
              bgcolor: 'primary.main',
              color: 'primary.contrastText',
              px: 2,
              py: 1.5,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            {/* Clickable header area */}
            <Box
              onClick={handleToggleExpanded}
              sx={{
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                flex: 1,
                cursor: 'pointer',
                '&:hover': {
                  opacity: 0.9,
                },
              }}
              role="button"
              aria-label={expanded ? 'Collapse checklist' : 'Expand checklist'}
              aria-expanded={expanded}
              tabIndex={0}
              onKeyDown={e => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  handleToggleExpanded();
                }
              }}
            >
              <LightbulbIcon
                sx={{ fontSize: 24, color: '#fff' }}
                aria-hidden="true"
              />
              <Typography
                variant="subtitle1"
                sx={{ fontWeight: 600, color: '#fff' }}
              >
                Getting Started
              </Typography>
              {incompletedSteps > 0 && (
                <Badge
                  badgeContent={incompletedSteps}
                  color="error"
                  sx={{
                    ml: 1,
                    '& .MuiBadge-badge': {
                      bgcolor: 'warning.main',
                      color: 'warning.contrastText',
                    },
                  }}
                  aria-label={`${incompletedSteps} incomplete ${incompletedSteps === 1 ? 'step' : 'steps'}`}
                />
              )}
            </Box>
            <Box sx={{ display: 'flex', alignItems: 'center' }}>
              <Tooltip title={expanded ? 'Collapse' : 'Expand'}>
                <IconButton
                  size="small"
                  onClick={handleToggleExpanded}
                  sx={{
                    color: '#fff',
                    transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                    transition: 'transform 0.3s',
                  }}
                  aria-label={expanded ? 'Collapse' : 'Expand'}
                >
                  <ExpandMoreIcon />
                </IconButton>
              </Tooltip>
              <Tooltip title="Dismiss">
                <IconButton
                  size="small"
                  onClick={handleDismissClick}
                  sx={{ color: '#fff' }}
                  aria-label="Dismiss onboarding"
                >
                  <CloseIcon />
                </IconButton>
              </Tooltip>
            </Box>
          </Box>

          <Collapse in={expanded}>
            <CardContent sx={{ p: 0 }}>
              {/* Progress bar */}
              <Box sx={{ px: 2, pt: 2, pb: 1 }}>
                <Box
                  sx={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    mb: 1,
                  }}
                >
                  <Typography variant="body2" color="text.secondary">
                    Progress
                  </Typography>
                  <Typography
                    variant="body2"
                    fontWeight={600}
                    aria-live="polite"
                    aria-atomic="true"
                  >
                    {completionPercentage}%
                  </Typography>
                </Box>
                <LinearProgress
                  variant="determinate"
                  value={completionPercentage}
                  sx={{
                    height: 8,
                    borderRadius: theme => theme.shape.borderRadius,
                    bgcolor: 'action.hover',
                  }}
                  aria-label={`Onboarding progress: ${completionPercentage}% complete`}
                />
              </Box>

              {/* Checklist */}
              <List sx={{ py: 0 }} aria-label="Onboarding steps">
                {ONBOARDING_STEPS.map((step, index) => {
                  const isCompleted = progress[step.id];
                  return (
                    <ListItem
                      key={step.id}
                      disablePadding
                      sx={{
                        borderTop: index > 0 ? 1 : 0,
                        borderColor: 'divider',
                      }}
                    >
                      <ListItemButton
                        onClick={() => handleStepClick(step)}
                        disabled={isCompleted}
                        sx={{
                          py: 1.5,
                          '&:hover': {
                            bgcolor: isCompleted
                              ? 'transparent'
                              : 'action.hover',
                          },
                        }}
                        aria-label={`${step.title}${step.optional ? ' (optional)' : ''}${isCompleted ? ' - completed' : ''}`}
                      >
                        <ListItemIcon sx={{ minWidth: 40 }}>
                          {isCompleted ? (
                            <CheckCircleIcon
                              color="success"
                              aria-label="Completed"
                            />
                          ) : (
                            <RadioButtonUncheckedIcon
                              color="action"
                              aria-label="Not completed"
                            />
                          )}
                        </ListItemIcon>
                        <ListItemText
                          primary={
                            <Typography
                              variant="body2"
                              sx={{
                                fontWeight: isCompleted ? 400 : 500,
                                textDecoration: isCompleted
                                  ? 'line-through'
                                  : 'none',
                                color: isCompleted
                                  ? 'text.secondary'
                                  : 'text.primary',
                              }}
                            >
                              {step.title}
                              {step.optional && (
                                <Typography
                                  component="span"
                                  variant="caption"
                                  sx={{ ml: 1, color: 'text.secondary' }}
                                >
                                  (optional)
                                </Typography>
                              )}
                            </Typography>
                          }
                          secondary={
                            !isCompleted && (
                              <Typography
                                variant="caption"
                                color="text.secondary"
                              >
                                {step.description}
                              </Typography>
                            )
                          }
                        />
                      </ListItemButton>
                    </ListItem>
                  );
                })}
              </List>
            </CardContent>
          </Collapse>
        </Card>
      </Box>

      {/* Confirmation Dialog */}
      <Dialog
        open={confirmDialogOpen}
        onClose={handleCancelDismiss}
        aria-labelledby="dismiss-dialog-title"
        aria-describedby="dismiss-dialog-description"
      >
        <DialogTitle id="dismiss-dialog-title">Dismiss Onboarding?</DialogTitle>
        <DialogContent>
          <DialogContentText id="dismiss-dialog-description">
            This will permanently hide the getting started guide.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCancelDismiss} color="primary">
            Cancel
          </Button>
          <Button
            onClick={handleConfirmDismiss}
            color="primary"
            variant="contained"
            autoFocus
          >
            Dismiss
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
}
