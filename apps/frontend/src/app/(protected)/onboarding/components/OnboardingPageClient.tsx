'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useSession, getCsrfToken } from 'next-auth/react';
import {
  Box,
  Paper,
  Stepper,
  Step,
  StepLabel,
  Typography,
  Container,
} from '@mui/material';
import OrganizationDetailsStep from './OrganizationDetailsStep';
import FinishStep from './FinishStep';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { OrganizationCreate } from '@/utils/api-client/organizations-client';
import { UUID } from 'crypto';
import { UserUpdate } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';

type OnboardingStatus = 'idle' | 'creating_organization' | 'updating_user' | 'loading_initial_data';

interface FormData {
  firstName: string;
  lastName: string;
  organizationName: string;
  website: string;
  invites: { email: string }[];
}

interface OnboardingPageClientProps {
  sessionToken: string;
  userId: UUID;
}

const steps = ['Organization Details', 'Finish'];

export default function OnboardingPageClient({ sessionToken, userId }: OnboardingPageClientProps) {
  const router = useRouter();
  const { data: session, update } = useSession();
  const notifications = useNotifications();
  const [activeStep, setActiveStep] = React.useState(0);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [onboardingStatus, setOnboardingStatus] = React.useState<OnboardingStatus>('idle');
  const [formData, setFormData] = React.useState<FormData>({
    firstName: '',
    lastName: '',
    organizationName: '',
    website: '',
    invites: [{ email: '' }]
  });

  const organizationsClient = new ApiClientFactory(sessionToken).getOrganizationsClient();
  const usersClient = new ApiClientFactory(sessionToken).getUsersClient();

  const handleNext = () => {
    setActiveStep((prevActiveStep) => prevActiveStep + 1);
  };

  const handleBack = () => {
    setActiveStep((prevActiveStep) => prevActiveStep - 1);
  };

  const handleComplete = async () => {
    try {
      setIsSubmitting(true);

      if (!userId) {
        throw new Error('Invalid user ID');
      }

      setOnboardingStatus('creating_organization');
      const organizationData: OrganizationCreate = {
        name: formData.organizationName,
        website: formData.website || undefined,
        owner_id: userId,
        user_id: userId,
        is_active: true,
        is_domain_verified: false
      };

      let organization;
      try {
        organization = await organizationsClient.createOrganization(organizationData);
        console.log('Organization creation response:', organization);
      } catch (orgError: any) {
        console.error('Organization creation error:', orgError);
        notifications.show(orgError?.message || 'Failed to create organization. Please try again.', { severity: 'error' });
        return;
      }

      setOnboardingStatus('updating_user');
      const userUpdate: UserUpdate = {
        given_name: formData.firstName,
        family_name: formData.lastName,
        name: `${formData.firstName} ${formData.lastName}`,
        organization_id: organization.id as UUID
      };

      let response;
      try {
        response = await usersClient.updateUser(userId, userUpdate);
      } catch (userError: any) {
        console.error('User update error:', userError);
        notifications.show(userError?.message || 'Failed to update user. Please try again.', { severity: 'error' });
        return;
      }

      if ('session_token' in response) {
        if (typeof window !== 'undefined') {
          const hostname = window.location.hostname;
          const isLocalhost = hostname === 'localhost' || hostname === '127.0.0.1';
          
          const cookieOptions = isLocalhost
            ? 'path=/; samesite=lax'
            : `domain=rhesis.ai; path=/; secure; samesite=lax`;
          
          document.cookie = `next-auth.session-token=${response.session_token}; ${cookieOptions}`;
        }

        try {
          setOnboardingStatus('loading_initial_data');
          const initDataResponse = await organizationsClient.loadInitialData(organization.id);
          
          if (initDataResponse.status === 'success') {
            notifications.show('Onboarding completed successfully!', { severity: 'success' });
            await new Promise(resolve => setTimeout(resolve, 1000));
            window.location.href = '/dashboard';
            return;
          } else {
            throw new Error('Failed to initialize organization data');
          }
        } catch (initError: any) {
          console.error('Initial data loading error:', initError);
          notifications.show(initError?.message || 'Failed to set up organization. Please contact support.', { severity: 'error' });
          setIsSubmitting(false);
          return;
        }
      } else {
        throw new Error('Invalid response from user update');
      }

    } catch (error: any) {
      console.error('Onboarding error:', error);
      notifications.show(error?.message || 'Failed to complete onboarding. Please try again.', { severity: 'error' });
    } finally {
      setIsSubmitting(false);
      setOnboardingStatus('idle');
    }
  };

  const updateFormData = (data: Partial<FormData>) => {
    setFormData((prev) => ({
      ...prev,
      ...data
    }));
  };

  const renderStep = () => {
    switch (activeStep) {
      case 0:
        return (
          <OrganizationDetailsStep
            formData={formData}
            updateFormData={updateFormData}
            onNext={handleNext}
          />
        );
      case 1:
        return (
          <FinishStep
            formData={formData}
            onComplete={handleComplete}
            onBack={handleBack}
            isSubmitting={isSubmitting}
            onboardingStatus={onboardingStatus}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Container maxWidth="lg">
      <Paper 
        elevation={0} 
        sx={{ 
          p: 4, 
          borderRadius: 2,
          width: '100%',
          maxWidth: 800,
          mx: 'auto'
        }}
      >
        <Box sx={{ width: '100%', mb: 4 }}>
          <Stepper activeStep={activeStep} alternativeLabel>
            {steps.map((label) => (
              <Step key={label}>
                <StepLabel>{label}</StepLabel>
              </Step>
            ))}
          </Stepper>
        </Box>
        
        {renderStep()}
      </Paper>
    </Container>
  );
} 