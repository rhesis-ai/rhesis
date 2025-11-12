'use client';

import React from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  LinearProgress,
  Button,
  Chip,
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  RadioButtonUnchecked as RadioButtonUncheckedIcon,
  Lightbulb as LightbulbIcon,
  ArrowForward as ArrowForwardIcon,
} from '@mui/icons-material';
import { useRouter } from 'next/navigation';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { OnboardingStep } from '@/types/onboarding';

const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'projectCreated',
    title: 'Create your first project',
    description: 'Organize your work by creating a project',
    targetPath: '/projects?tour=project',
    tourId: 'project',
  },
  {
    id: 'endpointSetup',
    title: 'Set up an endpoint',
    description: 'Connect to your AI service endpoint',
    targetPath: '/endpoints?tour=endpoint',
    tourId: 'endpoint',
  },
  {
    id: 'usersInvited',
    title: 'Invite team members',
    description: 'Collaborate with your team',
    optional: true,
    targetPath: '/organizations/team?tour=invite',
    tourId: 'invite',
  },
  {
    id: 'testCasesCreated',
    title: 'Create your first test cases',
    description: 'Define what to test in your endpoints',
    targetPath: '/tests?tour=testCases',
    tourId: 'testCases',
  },
];

export default function OnboardingDashboardCard() {
  const router = useRouter();
  const { progress, isComplete, completionPercentage, dismissOnboarding } =
    useOnboarding();

  // Don't show if dismissed or completed
  if (progress.dismissed || isComplete) {
    return null;
  }

  const handleStepClick = (step: OnboardingStep) => {
    router.push(step.targetPath);
  };

  const nextStep = ONBOARDING_STEPS.find(step => !progress[step.id]);

  return (
    <Card
      sx={{
        height: '100%',
        border: '2px solid',
        borderColor: 'primary.main',
        bgcolor: 'background.paper',
      }}
    >
      <CardContent>
        {/* Header */}
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
          <LightbulbIcon color="primary" sx={{ fontSize: 28 }} />
          <Typography variant="h6" fontWeight={600}>
            Getting Started with Rhesis
          </Typography>
        </Box>

        <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
          Complete these steps to get the most out of Rhesis
        </Typography>

        {/* Progress bar */}
        <Box sx={{ mb: 3 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Your Progress
            </Typography>
            <Typography variant="body2" fontWeight={600} color="primary">
              {completionPercentage}% Complete
            </Typography>
          </Box>
          <LinearProgress
            variant="determinate"
            value={completionPercentage}
            sx={{
              height: 10,
              borderRadius: 5,
              bgcolor: 'action.hover',
            }}
          />
        </Box>

        {/* Checklist */}
        <List sx={{ py: 0, mb: 2 }}>
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
                    py: 2,
                    '&:hover': {
                      bgcolor: isCompleted ? 'transparent' : 'action.hover',
                    },
                  }}
                >
                  <ListItemIcon sx={{ minWidth: 48 }}>
                    {isCompleted ? (
                      <CheckCircleIcon color="success" sx={{ fontSize: 28 }} />
                    ) : (
                      <RadioButtonUncheckedIcon
                        color="action"
                        sx={{ fontSize: 28 }}
                      />
                    )}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box
                        sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
                      >
                        <Typography
                          variant="body1"
                          sx={{
                            fontWeight: isCompleted ? 400 : 600,
                            textDecoration: isCompleted
                              ? 'line-through'
                              : 'none',
                            color: isCompleted
                              ? 'text.secondary'
                              : 'text.primary',
                          }}
                        >
                          {step.title}
                        </Typography>
                        {step.optional && (
                          <Chip
                            label="Optional"
                            size="small"
                            variant="outlined"
                            sx={{ height: 20 }}
                          />
                        )}
                      </Box>
                    }
                    secondary={
                      <Typography variant="body2" color="text.secondary">
                        {step.description}
                      </Typography>
                    }
                  />
                </ListItemButton>
              </ListItem>
            );
          })}
        </List>

        {/* Action buttons */}
        <Box sx={{ display: 'flex', gap: 1, justifyContent: 'space-between' }}>
          {nextStep && (
            <Button
              variant="contained"
              endIcon={<ArrowForwardIcon />}
              onClick={() => handleStepClick(nextStep)}
              fullWidth
            >
              Continue: {nextStep.title}
            </Button>
          )}
          <Button
            variant="text"
            onClick={dismissOnboarding}
            sx={{ minWidth: 'auto', whiteSpace: 'nowrap' }}
          >
            Dismiss
          </Button>
        </Box>
      </CardContent>
    </Card>
  );
}
