'use client';

import * as React from 'react';
import {
  Box,
  TextField,
  Button,
  IconButton,
  CircularProgress,
  Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import SendIcon from '@mui/icons-material/Send';
import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UUID } from 'crypto';

interface InviteItem {
  id: string;
  email: string;
}

interface FormData {
  invites: InviteItem[];
}

interface TeamInviteFormProps {
  onInvitesSent?: (emails: string[]) => void;
  disableDuringTour?: boolean;
  /** When true, submit is triggered by the parent drawer (no footer button). */
  embedded?: boolean;
  onSubmittingChange?: (submitting: boolean) => void;
}

function createInvite(email = ''): InviteItem {
  return { id: crypto.randomUUID(), email };
}

const TeamInviteForm = React.forwardRef<HTMLFormElement, TeamInviteFormProps>(
  function TeamInviteForm(
    {
      onInvitesSent,
      disableDuringTour = false,
      embedded = false,
      onSubmittingChange,
    },
    ref
  ) {
    const { data: session } = useSession();
    const notifications = useNotifications();

    const [formData, setFormData] = useState<FormData>({
      invites: [createInvite()],
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [errors, setErrors] = useState<{
      [key: string]: { hasError: boolean; message: string };
    }>({});

    useEffect(() => {
      onSubmittingChange?.(isSubmitting);
    }, [isSubmitting, onSubmittingChange]);

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const MAX_TEAM_MEMBERS = 10;

    const validateForm = () => {
      const newErrors: {
        [key: string]: { hasError: boolean; message: string };
      } = {};
      let hasError = false;

      const nonEmptyInvites = formData.invites.filter(invite =>
        invite.email.trim()
      );
      if (nonEmptyInvites.length > MAX_TEAM_MEMBERS) {
        notifications.show(
          `You can invite a maximum of ${MAX_TEAM_MEMBERS} team members at once.`,
          { severity: 'error' }
        );
        return false;
      }

      const emailsToCheck = formData.invites
        .map(invite => ({
          email: invite.email.trim().toLowerCase(),
          id: invite.id,
        }))
        .filter(item => item.email);

      const seenEmails = new Set<string>();
      const duplicateEmails = new Set<string>();

      emailsToCheck.forEach(({ email }) => {
        if (seenEmails.has(email)) {
          duplicateEmails.add(email);
        } else {
          seenEmails.add(email);
        }
      });

      formData.invites.forEach(invite => {
        const trimmedEmail = invite.email.trim();

        if (trimmedEmail) {
          if (!emailRegex.test(trimmedEmail)) {
            newErrors[invite.id] = {
              hasError: true,
              message: 'Please enter a valid email address',
            };
            hasError = true;
          } else if (duplicateEmails.has(trimmedEmail.toLowerCase())) {
            newErrors[invite.id] = {
              hasError: true,
              message: 'This email address is already added',
            };
            hasError = true;
          }
        }
      });

      setErrors(newErrors);
      return !hasError;
    };

    const handleSubmit = async (e: React.FormEvent) => {
      e.preventDefault();

      if (!validateForm()) {
        return;
      }

      if (!session?.session_token) {
        notifications.show('Session expired. Please refresh the page.', {
          severity: 'error',
        });
        return;
      }

      try {
        setIsSubmitting(true);

        const validEmails = formData.invites
          .map(invite => invite.email.trim())
          .filter(email => email);

        if (validEmails.length === 0) {
          notifications.show('Please enter at least one email address', {
            severity: 'error',
          });
          return;
        }

        const clientFactory = new ApiClientFactory(session.session_token);
        const usersClient = clientFactory.getUsersClient();

        const invitationResults: Array<{
          email: string;
          success: boolean;
          error?: string;
        }> = [];

        const createUserPromises = validEmails.map(async email => {
          const userData = {
            email: email,
            organization_id: session.user?.organization_id as UUID,
            is_active: true,
            send_invite: true,
          };

          try {
            const user = await usersClient.createUser(userData);
            invitationResults.push({ email, success: true });
            return user;
          } catch (error: unknown) {
            let errorMessage = 'Unknown error';
            let isExpectedError = false;

            if (error instanceof Error) {
              if (error.message.includes('API error:')) {
                const statusMatch = error.message.match(/API error: (\d+)/);
                const statusCode = statusMatch
                  ? parseInt(statusMatch[1])
                  : null;
                isExpectedError = statusCode
                  ? [400, 409, 422, 429].includes(statusCode)
                  : false;

                const match = error.message.match(/API error: \d+ - (.+)/);
                if (match && match[1]) {
                  try {
                    const parsed = JSON.parse(match[1]);
                    errorMessage = parsed.detail || parsed.message || match[1];
                  } catch {
                    errorMessage = match[1];
                  }
                } else {
                  errorMessage = error.message;
                }
              } else {
                errorMessage = error.message;
              }
            } else if (
              typeof error === 'object' &&
              error !== null &&
              'detail' in error
            ) {
              errorMessage = String((error as { detail: unknown }).detail);
            } else if (typeof error === 'string') {
              errorMessage = error;
            }

            if (!isExpectedError) {
              // unexpected errors logged by API client
            }

            invitationResults.push({
              email,
              success: false,
              error: errorMessage,
            });
            return null;
          }
        });

        await Promise.all(createUserPromises);
        const successCount = invitationResults.filter(
          result => result.success
        ).length;
        const failedCount = validEmails.length - successCount;

        if (successCount > 0 && failedCount === 0) {
          notifications.show(
            `Successfully sent ${successCount} invitation${successCount > 1 ? 's' : ''}!`,
            { severity: 'success' }
          );
        } else if (successCount > 0 && failedCount > 0) {
          const failedEmails = invitationResults
            .filter(result => !result.success)
            .map(result => result.email);

          const errorTypes = invitationResults
            .filter(result => !result.success)
            .map(result => result.error)
            .filter((error, index, arr) => arr.indexOf(error) === index);

          let errorSummary = '';
          if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('rate limit')
          ) {
            errorSummary = 'rate limit exceeded';
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already belongs to an organization')
          ) {
            errorSummary = `${failedEmails.join(', ')} already belong${failedEmails.length === 1 ? 's' : ''} to another organization`;
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already exists')
          ) {
            errorSummary = `${failedEmails.join(', ')} already exist${failedEmails.length === 1 ? 's' : ''}`;
          } else {
            errorSummary = `${failedEmails.join(', ')} failed`;
          }

          notifications.show(
            `Sent ${successCount} invitation${successCount > 1 ? 's' : ''}. ${errorSummary}.`,
            { severity: 'warning', autoHideDuration: 6000 }
          );
        } else {
          const failedEmails = invitationResults
            .filter(result => !result.success)
            .map(result => result.email);

          const errorTypes = invitationResults
            .filter(result => !result.success)
            .map(result => result.error)
            .filter((error, index, arr) => arr.indexOf(error) === index);

          let errorMessage = '';
          if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('rate limit')
          ) {
            errorMessage = errorTypes[0];
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already belongs to an organization')
          ) {
            if (failedEmails.length === 1) {
              errorMessage = `${failedEmails[0]} already belongs to another organization. They must leave their current organization first.`;
            } else {
              errorMessage = `${failedEmails.join(', ')} already belong to another organization. They must leave their current organizations first.`;
            }
          } else if (
            errorTypes.length === 1 &&
            errorTypes[0]?.includes('already exists')
          ) {
            if (failedEmails.length === 1) {
              errorMessage = `${failedEmails[0]} already exists.`;
            } else {
              errorMessage = `${failedEmails.join(', ')} already exist.`;
            }
          } else {
            errorMessage = `Failed to invite ${failedEmails.join(', ')}.`;
          }

          notifications.show(errorMessage, {
            severity: 'error',
            autoHideDuration: 6000,
          });
        }

        if (successCount > 0) {
          setFormData({ invites: [createInvite()] });
          setErrors({});

          if (onInvitesSent) {
            const successfulEmails = invitationResults
              .filter(result => result.success)
              .map(result => result.email);
            onInvitesSent(successfulEmails);
          }
        }
      } catch (_error) {
        notifications.show('Failed to send invitations. Please try again.', {
          severity: 'error',
        });
      } finally {
        setIsSubmitting(false);
      }
    };

    const handleEmailChange = (invite: InviteItem, value: string) => {
      setFormData(prev => ({
        invites: prev.invites.map(i =>
          i.id === invite.id ? { ...i, email: value } : i
        ),
      }));

      if (errors[invite.id]) {
        const newErrors = { ...errors };
        delete newErrors[invite.id];
        setErrors(newErrors);
      }
    };

    const addEmailField = () => {
      if (formData.invites.length >= MAX_TEAM_MEMBERS) {
        notifications.show(
          `You can invite a maximum of ${MAX_TEAM_MEMBERS} team members at once.`,
          { severity: 'error' }
        );
        return;
      }

      setFormData({
        invites: [...formData.invites, createInvite()],
      });
    };

    const removeEmailField = (invite: InviteItem) => {
      setFormData(prev => ({
        invites: prev.invites.filter(i => i.id !== invite.id),
      }));

      if (errors[invite.id]) {
        const newErrors = { ...errors };
        delete newErrors[invite.id];
        setErrors(newErrors);
      }
    };

    return (
      <Box component="form" ref={ref} onSubmit={handleSubmit}>
        <Stack spacing={2} sx={{ mb: embedded ? 0 : 3 }}>
          {formData.invites.map((invite, index) => {
            return (
              <Box
                key={invite.id}
                display="flex"
                alignItems="flex-start"
                gap={2}
              >
                <TextField
                  fullWidth
                  type="email"
                  label="Email Address"
                  value={invite.email}
                  onChange={e => handleEmailChange(invite, e.target.value)}
                  error={Boolean(errors[invite.id]?.hasError)}
                  helperText={errors[invite.id]?.message || ''}
                  placeholder="colleague@company.com"
                  variant="outlined"
                  size="small"
                  data-tour={index === 0 ? 'invite-email-input' : undefined}
                />
                {formData.invites.length > 1 && (
                  <IconButton
                    onClick={() => removeEmailField(invite)}
                    color="error"
                    size="small"
                  >
                    <DeleteIcon />
                  </IconButton>
                )}
              </Box>
            );
          })}

          <Box display="flex" justifyContent="flex-start">
            <Button
              startIcon={<AddIcon />}
              onClick={addEmailField}
              variant="outlined"
              size="small"
              disabled={formData.invites.length >= MAX_TEAM_MEMBERS}
            >
              {formData.invites.length >= MAX_TEAM_MEMBERS
                ? `Maximum ${MAX_TEAM_MEMBERS} invites reached`
                : 'Add Another Email'}
            </Button>
          </Box>
        </Stack>

        {!embedded && (
          <Box display="flex" justifyContent="flex-end">
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={isSubmitting || disableDuringTour}
              startIcon={
                isSubmitting ? (
                  <CircularProgress size={20} color="inherit" />
                ) : (
                  <SendIcon />
                )
              }
              data-tour="send-invites-button"
            >
              {isSubmitting ? 'Sending Invitations...' : 'Send Invitations'}
            </Button>
          </Box>
        )}
      </Box>
    );
  }
);

export default TeamInviteForm;
