'use client';

import React, { useState } from 'react';
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
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  RadioButtonUnchecked as RadioButtonUncheckedIcon,
  ExpandMore as ExpandMoreIcon,
  Close as CloseIcon,
  Lightbulb as LightbulbIcon,
} from '@mui/icons-material';
import { useRouter, usePathname } from 'next/navigation';
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

export default function OnboardingChecklist() {
  const router = useRouter();
  const pathname = usePathname();
  const { progress, isComplete, completionPercentage, dismissOnboarding } =
    useOnboarding();

  // Start collapsed by default, adjust based on pathname after mount
  const [expanded, setExpanded] = useState(false);
  const [visible, setVisible] = useState(true);

  // Update expanded state based on pathname after mount (avoid hydration issues)
  React.useEffect(() => {
    setExpanded(pathname !== '/dashboard');
  }, [pathname]);

  // Don't show if dismissed or completed
  if (progress.dismissed || isComplete || !visible) {
    return null;
  }

  const handleStepClick = (step: OnboardingStep) => {
    router.push(step.targetPath);
  };

  const handleDismiss = () => {
    dismissOnboarding();
    setVisible(false);
  };

  const incompletedSteps = ONBOARDING_STEPS.filter(
    step => !progress[step.id]
  ).length;

  return (
    <Box
      sx={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 1300,
        maxWidth: 380,
        width: '100%',
      }}
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
            onClick={() => setExpanded(!expanded)}
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
          >
            <LightbulbIcon sx={{ fontSize: 24, color: '#fff' }} />
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
              />
            )}
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center' }}>
            <Tooltip title={expanded ? 'Collapse' : 'Expand'}>
              <IconButton
                size="small"
                onClick={() => setExpanded(!expanded)}
                sx={{
                  color: '#fff',
                  transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)',
                  transition: 'transform 0.3s',
                }}
              >
                <ExpandMoreIcon />
              </IconButton>
            </Tooltip>
            <Tooltip title="Dismiss">
              <IconButton
                size="small"
                onClick={handleDismiss}
                sx={{ color: '#fff' }}
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
                sx={{ display: 'flex', justifyContent: 'space-between', mb: 1 }}
              >
                <Typography variant="body2" color="text.secondary">
                  Progress
                </Typography>
                <Typography variant="body2" fontWeight={600}>
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
              />
            </Box>

            {/* Checklist */}
            <List sx={{ py: 0 }}>
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
                          bgcolor: isCompleted ? 'transparent' : 'action.hover',
                        },
                      }}
                    >
                      <ListItemIcon sx={{ minWidth: 40 }}>
                        {isCompleted ? (
                          <CheckCircleIcon color="success" />
                        ) : (
                          <RadioButtonUncheckedIcon color="action" />
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
  );
}
