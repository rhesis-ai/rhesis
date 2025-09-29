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
  Stack,
} from '@mui/material';
import OrganizationDetailsStep from './OrganizationDetailsStep';
import InviteTeamStep from './InviteTeamStep';
import FinishStep from './FinishStep';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { OrganizationCreate } from '@/utils/api-client/organizations-client';
import { UUID } from 'crypto';
import { UserUpdate, UserCreate } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';

type OnboardingStatus =
  | 'idle'
  | 'creating_organization'
  | 'updating_user'
  | 'loading_initial_data';

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

const steps = ['Organization Details', 'Invite Team', 'Finish'];

export default function OnboardingPageClient({
  sessionToken,
  userId,
}: OnboardingPageClientProps) {
  const router = useRouter();
  const { data: session, update } = useSession();
  const notifications = useNotifications();
  const [activeStep, setActiveStep] = React.useState(0);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [onboardingStatus, setOnboardingStatus] =
    React.useState<OnboardingStatus>('idle');
  const [formData, setFormData] = React.useState<FormData>({
    firstName: '',
    lastName: '',
    organizationName: '',
    website: '',
    invites: [{ email: '' }],
  });

  const organizationsClient = new ApiClientFactory(
    sessionToken
  ).getOrganizationsClient();
  const usersClient = new ApiClientFactory(sessionToken).getUsersClient();

  const handleNext = () => {
    setActiveStep(prevActiveStep => prevActiveStep + 1);
  };

  const handleBack = () => {
    setActiveStep(prevActiveStep => prevActiveStep - 1);
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
        is_domain_verified: false,
      };

      let organization;
      try {
        organization =
          await organizationsClient.createOrganization(organizationData);
        console.log('Organization creation response:', organization);
      } catch (orgError: any) {
        setIsSubmitting(false);
        console.error('Organization creation error:', orgError);
        notifications.show(
          orgError?.message ||
            'Failed to create organization. Please try again.',
          { severity: 'error' }
        );
        return;
      }

      setOnboardingStatus('updating_user');
      const userUpdate: UserUpdate = {
        given_name: formData.firstName,
        family_name: formData.lastName,
        name: `${formData.firstName} ${formData.lastName}`,
        organization_id: organization.id as UUID,
      };

      let response;
      try {
        response = await usersClient.updateUser(userId, userUpdate);
      } catch (userError: any) {
        setIsSubmitting(false);
        console.error('User update error:', userError);
        notifications.show(
          userError?.message || 'Failed to update user. Please try again.',
          { severity: 'error' }
        );
        return;
      }

      if ('session_token' in response) {
        if (typeof window !== 'undefined') {
          const hostname = window.location.hostname;
          const isLocalhost =
            hostname === 'localhost' || hostname === '127.0.0.1';

          const cookieOptions = isLocalhost
            ? 'path=/; samesite=lax'
            : `domain=rhesis.ai; path=/; secure; samesite=lax`;

          document.cookie = `next-auth.session-token=${response.session_token}; ${cookieOptions}`;
        }

        // Create invited users and send invitation emails now that we have the organization
        try {
          const validEmails = formData.invites
            .filter(invite => invite.email.trim())
            .map(invite => invite.email.trim());

          if (validEmails.length > 0) {
            const invitationResults: Array<{
              email: string;
              success: boolean;
              error?: string;
            }> = [];

            const createUserPromises = validEmails.map(async email => {
              const userData = {
                email: email,
                organization_id: organization.id as UUID,
                is_active: true,
                send_invite: true, // This will trigger the invitation email
              };

              try {
                const user = await usersClient.createUser(userData);
                invitationResults.push({ email, success: true });
                return user;
              } catch (error: any) {
                let errorMessage = 'Unknown error';

                // Extract meaningful error messages
                if (error?.message) {
                  errorMessage = error.message;
                } else if (error?.detail) {
                  errorMessage = error.detail;
                } else if (typeof error === 'string') {
                  errorMessage = error;
                }

                console.error(
                  `Failed to create user with email ${email}:`,
                  error
                );
                invitationResults.push({
                  email,
                  success: false,
                  error: errorMessage,
                });
                return null;
              }
            });

            // Create all users in parallel
            const createdUsers = await Promise.all(createUserPromises);
            const successCount = createdUsers.filter(
              user => user !== null
            ).length;
            const failedCount = validEmails.length - successCount;

            // Provide detailed feedback
            if (successCount > 0 && failedCount === 0) {
              notifications.show(
                `Successfully invited ${successCount} team member${successCount === 1 ? '' : 's'}!`,
                { severity: 'success' }
              );
            } else if (successCount > 0 && failedCount > 0) {
              setIsSubmitting(false);
              notifications.show(
                `Successfully invited ${successCount} team member${successCount === 1 ? '' : 's'}. ${failedCount} invitation${failedCount === 1 ? '' : 's'} failed.`,
                { severity: 'warning' }
              );

              // Show specific errors for failed invitations
              const failedInvitations = invitationResults.filter(
                result => !result.success
              );
              failedInvitations.forEach(failed => {
                notifications.show(
                  `Failed to invite ${failed.email}: ${failed.error}`,
                  { severity: 'error' }
                );
              });
            } else if (failedCount > 0) {
              setIsSubmitting(false);
              notifications.show(
                `Failed to send all ${failedCount} invitation${failedCount === 1 ? '' : 's'}. Please try again.`,
                { severity: 'error' }
              );
            }
          }
        } catch (error: any) {
          setIsSubmitting(false);
          console.error('Error creating invited users:', error);
          const errorMessage =
            error?.message ||
            error?.detail ||
            'Unknown error occurred while sending invitations';
          notifications.show(`Warning: ${errorMessage}`, {
            severity: 'warning',
          });
          // Don't block onboarding completion for user creation errors
        }

        try {
          setOnboardingStatus('loading_initial_data');
          const initDataResponse = await organizationsClient.loadInitialData(
            organization.id
          );

          if (initDataResponse.status === 'success') {
            notifications.show('Onboarding completed successfully!', {
              severity: 'success',
            });
            await new Promise(resolve => setTimeout(resolve, 1000));
            window.location.href = '/dashboard';
            return;
          } else {
            throw new Error('Failed to initialize organization data');
          }
        } catch (initError: any) {
          setIsSubmitting(false);
          console.error('Initial data loading error:', initError);
          notifications.show(
            initError?.message ||
              'Failed to set up organization. Please contact support.',
            { severity: 'error' }
          );
          return;
        }
      } else {
        throw new Error('Invalid response from user update');
      }
    } catch (error: any) {
      setIsSubmitting(false);
      console.error('Onboarding error:', error);
      notifications.show(
        error?.message || 'Failed to complete onboarding. Please try again.',
        { severity: 'error' }
      );
    } finally {
      setOnboardingStatus('idle');
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
          <OrganizationDetailsStep
            formData={formData}
            updateFormData={updateFormData}
            onNext={handleNext}
          />
        );
      case 1:
        return (
          <InviteTeamStep
            formData={formData}
            updateFormData={updateFormData}
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 2:
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
    <Container maxWidth="md">
      <Box py={4}>
        {/* Header */}
        <Box textAlign="center" mb={4}>
          <Typography variant="h4" component="h1" gutterBottom color="primary">
            Welcome to Rhesis
          </Typography>
          <Typography variant="body1" color="text.secondary">
            Let&apos;s get your workspace set up in just a few steps
          </Typography>
        </Box>

        {/* Stepper */}
        <Box mb={4}>
          <Paper variant="outlined" elevation={0}>
            <Box p={3}>
              <Stepper activeStep={activeStep} alternativeLabel>
                {steps.map(label => (
                  <Step key={label}>
                    <StepLabel>{label}</StepLabel>
                  </Step>
                ))}
              </Stepper>
            </Box>
          </Paper>
        </Box>

        {/* Step Content */}
        <Box>{renderStep()}</Box>
      </Box>
    </Container>
  );
}
