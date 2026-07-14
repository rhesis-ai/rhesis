'use client';

import * as React from 'react';
import { signIn } from 'next-auth/react';
import OrganizationDetailsStep from './OrganizationDetailsStep';
import InviteTeamStep from './InviteTeamStep';
import FinishStep from './FinishStep';
import WelcomeVideoStep from './WelcomeVideoStep';
import OnboardingShell from './OnboardingShell';
import { ONBOARDING_STEP_COUNT } from './onboarding-steps';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { safeRandomUUID } from '@/utils/uuid';
import { OrganizationCreate } from '@/utils/api-client/organizations-client';
import { ProjectCreate } from '@/utils/api-client/interfaces/project';
import { UUID } from 'crypto';
import { UserUpdate } from '@/utils/api-client/interfaces/user';
import { useNotifications } from '@/components/common/NotificationContext';
import { writeActiveProjectId } from '@/utils/active-project';

type OnboardingStatus =
  | 'idle'
  | 'creating_organization'
  | 'updating_user'
  | 'loading_initial_data'
  | 'creating_project'
  | 'completed';

interface FormData {
  firstName: string;
  lastName: string;
  organizationName: string;
  projectName: string;
  website: string;
  invites: { id: string; email: string }[];
}

interface OnboardingPageClientProps {
  sessionToken: string;
  userId: UUID;
  videoUrl?: string;
}

export default function OnboardingPageClient({
  sessionToken,
  userId,
  videoUrl,
}: OnboardingPageClientProps) {
  const notifications = useNotifications();
  const [activeStep, setActiveStep] = React.useState(0);
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [onboardingStatus, setOnboardingStatus] =
    React.useState<OnboardingStatus>('idle');
  const [formData, setFormData] = React.useState<FormData>({
    firstName: '',
    lastName: '',
    organizationName: '',
    projectName: '',
    website: '',
    invites: [{ id: safeRandomUUID(), email: '' }],
  });

  const organizationsClient = new ApiClientFactory(
    sessionToken
  ).getOrganizationsClient();
  const usersClient = new ApiClientFactory(sessionToken).getUsersClient();

  const completingRef = React.useRef(false);

  const handleNext = () => {
    setActiveStep(prev => Math.min(prev + 1, ONBOARDING_STEP_COUNT - 1));
  };

  const handleBack = () => {
    setActiveStep(prev => Math.max(prev - 1, 0));
  };

  const handleComplete = async () => {
    if (completingRef.current || isSubmitting) {
      return;
    }

    completingRef.current = true;

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
      } catch (orgError: unknown) {
        completingRef.current = false;
        setIsSubmitting(false);
        notifications.show(
          orgError instanceof Error
            ? orgError.message
            : 'Failed to create organization. Please try again.',
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
      } catch (userError: unknown) {
        completingRef.current = false;
        setIsSubmitting(false);
        notifications.show(
          userError instanceof Error
            ? userError.message
            : 'Failed to update user. Please try again.',
          { severity: 'error' }
        );
        return;
      }

      if ('session_token' in response) {
        const activeSessionToken = response.session_token;
        const signInResult = await signIn('credentials', {
          session_token: activeSessionToken,
          refresh_token:
            (response as { refresh_token?: string }).refresh_token || '',
          redirect: false,
        });

        if (signInResult?.error) {
          throw new Error('Failed to establish session after onboarding');
        }

        const authenticatedFactory = new ApiClientFactory(activeSessionToken);
        const authenticatedUsersClient = authenticatedFactory.getUsersClient();
        const authenticatedOrganizationsClient =
          authenticatedFactory.getOrganizationsClient();
        const authenticatedProjectsClient =
          authenticatedFactory.getProjectsClient();

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
                send_invite: true,
              };

              try {
                const user =
                  await authenticatedUsersClient.createUser(userData);
                invitationResults.push({ email, success: true });
                return user;
              } catch (error: unknown) {
                let errorMessage = 'Unknown error';

                if (error instanceof Error) {
                  errorMessage = error.message;
                } else if (
                  typeof error === 'object' &&
                  error !== null &&
                  'detail' in error
                ) {
                  errorMessage = String((error as { detail: unknown }).detail);
                } else if (typeof error === 'string') {
                  errorMessage = error;
                }

                invitationResults.push({
                  email,
                  success: false,
                  error: errorMessage,
                });
                return null;
              }
            });

            const createdUsers = await Promise.all(createUserPromises);
            const successCount = createdUsers.filter(
              user => user !== null
            ).length;
            const failedCount = validEmails.length - successCount;

            if (successCount > 0 && failedCount === 0) {
              notifications.show(
                `Successfully invited ${successCount} team member${successCount === 1 ? '' : 's'}!`,
                { severity: 'success' }
              );
            } else if (successCount > 0 && failedCount > 0) {
              notifications.show(
                `Successfully invited ${successCount} team member${successCount === 1 ? '' : 's'}. ${failedCount} invitation${failedCount === 1 ? '' : 's'} failed.`,
                { severity: 'warning' }
              );

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
              notifications.show(
                `Failed to send all ${failedCount} invitation${failedCount === 1 ? '' : 's'}. Please try again.`,
                { severity: 'error' }
              );
            }
          }
        } catch (error: unknown) {
          const errorMessage =
            error instanceof Error
              ? error.message
              : 'Unknown error occurred while sending invitations';
          notifications.show(`Warning: ${errorMessage}`, {
            severity: 'warning',
          });
        }

        try {
          setOnboardingStatus('loading_initial_data');
          const initDataResponse =
            await authenticatedOrganizationsClient.loadInitialData(
              organization.id
            );

          if (initDataResponse.status !== 'success') {
            throw new Error('Failed to initialize organization data');
          }

          setOnboardingStatus('creating_project');
          const projectData: ProjectCreate = {
            name: formData.projectName.trim(),
            user_id: userId,
            owner_id: userId,
            organization_id: organization.id as UUID,
            is_active: true,
            icon: 'SmartToy',
          };

          const createdProject =
            await authenticatedProjectsClient.createProject(projectData);

          writeActiveProjectId(String(createdProject.id));
          await authenticatedUsersClient.updateUserSettings({
            default_project: {
              project_id: createdProject.id as UUID,
              name: createdProject.name,
            },
          });

          setOnboardingStatus('completed');
          notifications.show('Onboarding completed successfully!', {
            severity: 'success',
          });
          await new Promise(resolve => setTimeout(resolve, 1000));
          window.location.href = '/architect';
          return;
        } catch (initError: unknown) {
          completingRef.current = false;
          setIsSubmitting(false);
          setOnboardingStatus('idle');
          notifications.show(
            initError instanceof Error
              ? initError.message
              : 'Failed to set up organization. Please contact support.',
            { severity: 'error' }
          );
          return;
        }
      } else {
        throw new Error('Invalid response from user update');
      }
    } catch (error: unknown) {
      completingRef.current = false;
      setIsSubmitting(false);
      setOnboardingStatus('idle');
      notifications.show(
        error instanceof Error
          ? error.message
          : 'Failed to complete onboarding. Please try again.',
        { severity: 'error' }
      );
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
            sessionToken={sessionToken}
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
            onNext={handleNext}
            onBack={handleBack}
          />
        );
      case 3:
        return (
          <WelcomeVideoStep
            onComplete={handleComplete}
            onBack={handleBack}
            isSubmitting={isSubmitting}
            onboardingStatus={onboardingStatus}
            videoUrl={videoUrl}
          />
        );
      default:
        return null;
    }
  };

  return (
    <OnboardingShell activeStep={activeStep}>{renderStep()}</OnboardingShell>
  );
}
