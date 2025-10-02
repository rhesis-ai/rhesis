'use client';

import React, { useState } from 'react';
import {
  Box,
  Dialog,
  DialogTitle,
  DialogContent,
  Stepper,
  Step,
  StepLabel,
  IconButton,
  Typography,
  useTheme,
} from '@mui/material';
import { Close as CloseIcon } from '@mui/icons-material';
import { useNotifications } from '@/components/common/NotificationContext';

// Import step components
import TestGenerationLanding from '../generate/components/TestGenerationLanding';
import DescribeTestRequirements from '../generate/describe/components/DescribeTestRequirements';
import TestConfiguration from '../generate/configure/components/TestConfiguration';
import ConfirmTestGeneration from '../generate/confirm/components/ConfirmTestGeneration';

interface TestGenerationModalProps {
  open: boolean;
  onClose: () => void;
  sessionToken: string;
}

const steps = [
  { label: 'Choose Generation Type', key: 'landing' },
  { label: 'Describe Requirements', key: 'describe' },
  { label: 'Configure Tests', key: 'configure' },
  { label: 'Confirm Generation', key: 'confirm' },
];

export default function TestGenerationModal({
  open,
  onClose,
  sessionToken,
}: TestGenerationModalProps) {
  const theme = useTheme();
  const { show } = useNotifications();

  const [activeStep, setActiveStep] = useState(0);
  const [completed, setCompleted] = useState<Record<string, boolean>>({});

  // State for different steps

  const handleNext = () => {
    if (activeStep < steps.length - 1) {
      setActiveStep(activeStep + 1);
    }
  };

  const handleBack = () => {
    if (activeStep > 0) {
      setActiveStep(activeStep - 1);
    }
  };

  const handleStepComplete = (stepKey: string) => {
    setCompleted(prev => ({ ...prev, [stepKey]: true }));
    handleNext();
  };

  const handleGenerationTypeSelect = (type: 'manual' | 'ai') => {
    if (type === 'ai') {
      setActiveStep(1); // Go to describe step for AI generation
    } else {
      // Handle manual generation - redirect or show different flow
      show('Manual generation would redirect to different flow', {
        severity: 'info',
      });
    }
  };

  const handleClose = () => {
    setActiveStep(0);
    setCompleted({});
    onClose();
  };

  const renderStepContent = () => {
    switch (activeStep) {
      case 0:
        return (
          <TestGenerationLanding
            sessionToken={sessionToken}
            onGenerationTypeSelect={handleGenerationTypeSelect}
          />
        );
      case 1:
        return (
          <DescribeTestRequirements
            sessionToken={sessionToken}
            onNext={() => handleStepComplete('describe')}
            onBack={handleBack}
          />
        );
      case 2:
        return (
          <TestConfiguration
            sessionToken={sessionToken}
            onNext={() => handleStepComplete('configure')}
            onBack={handleBack}
          />
        );
      case 3:
        return (
          <ConfirmTestGeneration
            sessionToken={sessionToken}
            onGenerateComplete={() => {
              show('Test generation completed successfully!', {
                severity: 'success',
              });
              handleClose();
            }}
            onBack={handleBack}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      maxWidth="lg"
      fullWidth
      PaperProps={{
        sx: {
          height: '90vh',
          borderRadius: theme.shape.borderRadius,
        },
      }}
    >
      <DialogTitle
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          pb: 1,
        }}
      >
        <Typography variant="h6" component="div">
          Test Generation Wizard
        </Typography>
        <IconButton
          aria-label="close"
          onClick={handleClose}
          sx={{
            color: theme.palette.grey[500],
          }}
        >
          <CloseIcon />
        </IconButton>
      </DialogTitle>

      <DialogContent
        sx={{
          display: 'flex',
          flexDirection: 'column',
          p: 0,
          overflow: 'hidden',
        }}
      >
        {/* Stepper */}
        <Box sx={{ px: 3, pt: 2, pb: 1 }}>
          <Stepper activeStep={activeStep} alternativeLabel>
            {steps.map((step, index) => (
              <Step key={step.key} completed={completed[step.key]}>
                <StepLabel>{step.label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>

        {/* Step Content */}
        <Box
          sx={{
            flex: 1,
            overflow: 'auto',
            pt: activeStep === 0 ? 3 : 0, // Add padding for landing step
          }}
        >
          {renderStepContent()}
        </Box>
      </DialogContent>
    </Dialog>
  );
}
