'use client';

import React, { useCallback } from 'react';
import {
  Box,
  Button,
  Divider,
  LinearProgress,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  RadioButtonUnchecked as RadioButtonUncheckedIcon,
} from '@mui/icons-material';
import { useRouter } from 'next/navigation';
import { useSession } from 'next-auth/react';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { OnboardingStep } from '@/types/onboarding';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ONBOARDING_STEPS,
  REQUIRED_ONBOARDING_STEPS,
} from '@/config/onboarding-tours';

interface OnboardingChecklistProps {
  /** Called before navigating to a step, so the host can close itself. */
  onStepSelected?: () => void;
  onDismiss: () => void;
}

/** The checklist body: progress and steps. The sidebar row hosts it in a popover. */
export default function OnboardingChecklist({
  onStepSelected,
  onDismiss,
}: OnboardingChecklistProps) {
  const router = useRouter();
  const { data: session } = useSession();
  const { progress, completionPercentage } = useOnboarding();

  const doneCount = REQUIRED_ONBOARDING_STEPS.filter(
    step => progress[step.id]
  ).length;

  const handleStepClick = useCallback(
    async (step: OnboardingStep) => {
      onStepSelected?.();
      try {
        // Steps that need a project start their tour on the first project
        if (step.requiresProjects && session?.user) {
          try {
            const apiFactory = new ApiClientFactory();
            const projectsClient = apiFactory.getProjectsClient();
            const response = await projectsClient.getProjects();
            const projects = Array.isArray(response)
              ? response
              : response?.data || [];

            if (projects.length > 0 && step.tourId) {
              router.push(`/projects/${projects[0].id}?tour=${step.tourId}`);
              return;
            }
          } catch (error) {
            console.error('Error fetching projects for onboarding:', error);
          }
        }

        router.push(step.targetPath);
      } catch (error) {
        console.error('Failed to navigate to onboarding step:', error);
      }
    },
    [router, session, onStepSelected]
  );

  return (
    <Box sx={{ width: 320 }}>
      <Box sx={{ px: 2, pt: 0.5, pb: 1.5 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 700 }}>
          Getting started
        </Typography>
        <Typography
          variant="caption"
          sx={{ color: theme => theme.palette.greyscale.label }}
          aria-live="polite"
          aria-atomic="true"
        >
          {doneCount} of {REQUIRED_ONBOARDING_STEPS.length} done
        </Typography>
        <LinearProgress
          variant="determinate"
          value={completionPercentage}
          sx={{ mt: 1, height: 6, borderRadius: 3 }}
          aria-label={`Onboarding progress: ${completionPercentage}% complete`}
        />
      </Box>

      <List sx={{ py: 0 }} aria-label="Onboarding steps">
        {ONBOARDING_STEPS.map(step => {
          const isCompleted = progress[step.id];
          return (
            <ListItem key={step.id} disablePadding>
              <ListItemButton
                onClick={() => handleStepClick(step)}
                disabled={isCompleted}
                sx={{ py: 1, alignItems: 'flex-start' }}
                aria-label={`${step.title}${step.optional ? ' (optional)' : ''}${isCompleted ? ' - completed' : ''}`}
              >
                <ListItemIcon sx={{ minWidth: 36, mt: 0.25 }}>
                  {isCompleted ? (
                    <CheckCircleIcon color="success" aria-label="Completed" />
                  ) : (
                    <RadioButtonUncheckedIcon
                      color="action"
                      aria-label="Not completed"
                    />
                  )}
                </ListItemIcon>
                <ListItemText
                  sx={{ my: 0 }}
                  primary={
                    <Typography
                      variant="body2"
                      sx={{
                        fontWeight: isCompleted ? 400 : 600,
                        textDecoration: isCompleted ? 'line-through' : 'none',
                        color: isCompleted ? 'text.secondary' : 'text.primary',
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
                      <Typography variant="caption" color="text.secondary">
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

      <Divider sx={{ my: 0.75 }} />
      <Box sx={{ px: 1 }}>
        <Button
          size="small"
          onClick={onDismiss}
          sx={{ color: theme => theme.palette.greyscale.label }}
        >
          Hide this guide
        </Button>
      </Box>
    </Box>
  );
}
