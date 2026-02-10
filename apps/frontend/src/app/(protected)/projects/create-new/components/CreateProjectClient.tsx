'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Typography,
  Container,
  Snackbar,
  Alert,
  useTheme,
} from '@mui/material';
import ProjectDetailsStep from './ProjectDetailsStep';
import FinishStep from './FinishStep';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { ProjectCreate } from '@/utils/api-client/interfaces/project';
import { UUID } from 'crypto';

interface FormData {
  projectName: string;
  description: string;
  icon: string;
  owner_id?: string;
}

const steps = ['Project Details', 'Finish'];

interface CreateProjectClientProps {
  sessionToken: string;
  userId: UUID;
  organizationId?: UUID;
  userName: string;
  userImage: string;
}

export default function CreateProjectClient({
  sessionToken,
  userId,
  organizationId,
  userName,
  userImage,
}: CreateProjectClientProps) {
  const router = useRouter();
  const theme = useTheme();
  const [activeStep, setActiveStep] = React.useState(0);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [formData, setFormData] = React.useState<FormData>({
    projectName: '',
    description: '',
    icon: 'SmartToy', // Default icon
    owner_id: userId,
  });

  const projectsClient = new ApiClientFactory(sessionToken).getProjectsClient();

  const handleNext = () => {
    setActiveStep(prevActiveStep => prevActiveStep + 1);
  };

  const handleBack = () => {
    setActiveStep(prevActiveStep => prevActiveStep - 1);
  };

  const handleComplete = async () => {
    try {
      setIsSubmitting(true);
      setError(null);

      // Validate user ID before sending
      if (!userId) {
        throw new Error('Invalid user ID');
      }

      // Check for organization ID
      if (!organizationId) {
        // Show a specific error for missing organization ID
        setError(
          'Organization ID is required. Please complete the onboarding process to create an organization first.'
        );
        setIsSubmitting(false);
        return;
      }

      // Validate required form fields
      if (!formData.projectName.trim()) {
        setError('Project name is required');
        setIsSubmitting(false);
        return;
      }

      // Create project with required fields
      const projectData: ProjectCreate = {
        name: formData.projectName,
        description: formData.description,
        user_id: userId,
        owner_id: formData.owner_id ? (formData.owner_id as UUID) : userId,
        organization_id: organizationId,
        is_active: true,
        icon: formData.icon,
      };

      try {
        const _project = await projectsClient.createProject(projectData);

        // Navigate to the projects page
        router.push('/projects');
      } catch (projectError) {
        if (projectError instanceof Error) {
          if (projectError.message.includes('Failed to fetch')) {
            setError(
              'Network error: Could not reach the API server. Please check your connection or try again later.'
            );
          } else if (projectError.message.includes('API error')) {
            setError(`API Error: ${projectError.message}`);
          } else if (projectError.message.includes('already exists')) {
            setError(
              'A project with this name already exists. Please choose a different name.'
            );
          } else {
            setError(`Error creating project: ${projectError.message}`);
          }
        } else {
          setError('An unknown error occurred while creating the project.');
        }
      }
    } catch (_error) {
      setError('Failed to complete project creation. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const updateFormData = (data: Partial<FormData>) => {
    setFormData(prev => ({
      ...prev,
      ...data,
    }));
  };

  const renderStep = () => {
    switch (activeStep) {
      case 0:
        return (
          <ProjectDetailsStep
            formData={formData}
            updateFormData={updateFormData}
            onNext={handleNext}
            userName={userName}
            userImage={userImage}
            sessionToken={sessionToken}
            userId={userId}
          />
        );
      case 1:
        return (
          <FinishStep
            formData={formData}
            onComplete={handleComplete}
            onBack={handleBack}
            isSubmitting={isSubmitting}
            sessionToken={sessionToken}
          />
        );
      default:
        return null;
    }
  };

  const handleCloseError = () => {
    setError(null);
  };

  return (
    <Container
      maxWidth="lg"
      sx={{
        p: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
      }}
    >
      <Paper
        elevation={0}
        sx={{
          pt: 2,
          pb: 3,
          px: 3,
          borderRadius: theme.shape.borderRadius,
          width: '100%',
          maxWidth: 800,
          minWidth: 800,
        }}
      >
        <Typography variant="h4" align="center" sx={{ mb: 3 }}>
          Create New Project
        </Typography>

        <Box sx={{ width: '100%', mb: 4 }}>
          <Stepper activeStep={activeStep} alternativeLabel>
            {steps.map(label => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>

        {renderStep()}
      </Paper>

      <Snackbar
        open={!!error}
        autoHideDuration={6000}
        onClose={handleCloseError}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={handleCloseError}
          severity="error"
          sx={{ width: '100%' }}
        >
          {error}
        </Alert>
      </Snackbar>
    </Container>
  );
}
