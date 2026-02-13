import * as React from 'react';
import {
  Box,
  TextField,
  Button,
  Typography,
  IconButton,
  CircularProgress,
  Stack,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import SendIcon from '@mui/icons-material/Send';
import { useState } from 'react';
import { useSession } from 'next-auth/react';
import { useNotifications } from '@/components/common/NotificationContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { UUID } from 'crypto';

interface FormData {
  invites: { email: string }[];
}

interface TeamInviteFormProps {
  onInvitesSent?: (emails: string[]) => void;
  disableDuringTour?: boolean;
}

export default function TeamInviteForm({
  onInvitesSent,
  disableDuringTour = false,
}: TeamInviteFormProps) {
  const { data: session } = useSession();
  const notifications = useNotifications();

  const [formData, setFormData] = useState<FormData>({
    invites: [{ email: '' }],
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errors, setErrors] = useState<{
    [key: number]: { hasError: boolean; message: string };
  }>({});

  // Email validation regex
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

  // Maximum number of team members that can be invited
  const MAX_TEAM_MEMBERS = 10;

  const validateForm = () => {
    const newErrors: { [key: number]: { hasError: boolean; message: string } } =
      {};
    let hasError = false;

    // Check maximum team size
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

    // Get all non-empty emails for duplicate checking
    const emailsToCheck = formData.invites
      .map((invite, index) => ({
        email: invite.email.trim().toLowerCase(),
        index,
      }))
      .filter(item => item.email);

    // Check for duplicates
    const seenEmails = new Set<string>();
    const duplicateEmails = new Set<string>();

    emailsToCheck.forEach(({ email, index: _index }) => {
      if (seenEmails.has(email)) {
        duplicateEmails.add(email);
      } else {
        seenEmails.add(email);
      }
    });

    // Validate each email
    formData.invites.forEach((invite, index) => {
      const trimmedEmail = invite.email.trim();

      if (trimmedEmail) {
        // Check email format
        if (!emailRegex.test(trimmedEmail)) {
          newErrors[index] = {
            hasError: true,
            message: 'Please enter a valid email address',
          };
          hasError = true;
        }
        // Check for duplicates
        else if (duplicateEmails.has(trimmedEmail.toLowerCase())) {
          newErrors[index] = {
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

      // Get valid emails
      const validEmails = formData.invites
        .map(invite => invite.email.trim())
        .filter(email => email);

      if (validEmails.length === 0) {
        notifications.show('Please enter at least one email address', {
          severity: 'error',
        });
        return;
      }

      // Create API client
      const clientFactory = new ApiClientFactory(session.session_token);
      const usersClient = clientFactory.getUsersClient();

      // Send invitations
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

          // Extract meaningful error messages from different error formats
          if (error instanceof Error) {
            // Handle API error messages that might contain JSON
            if (error.message.includes('API error:')) {
              // Extract the status code and message
              const statusMatch = error.message.match(/API error: (\d+)/);
              const statusCode = statusMatch ? parseInt(statusMatch[1]) : null;

              // 400, 409, 422, 429 are expected client/validation errors
              isExpectedError = statusCode
                ? [400, 409, 422, 429].includes(statusCode)
                : false;

              // Extract the actual error message after "API error: status -"
              const match = error.message.match(/API error: \d+ - (.+)/);
              if (match && match[1]) {
                try {
                  // Try to parse as JSON first
                  const parsed = JSON.parse(match[1]);
                  errorMessage = parsed.detail || parsed.message || match[1];
                } catch {
                  // If not JSON, use the raw message
                  errorMessage = match[1];
                }
              } else {
                errorMessage = error.message;
              }
            } else {
              errorMessage = error.message;
            }
          } else if (typeof error === 'object' && error !== null && 'detail' in error) {
            errorMessage = String((error as { detail: unknown }).detail);
          } else if (typeof error === 'string') {
            errorMessage = error;
          }

          // Log expected validation errors as warnings, unexpected errors as errors
          if (isExpectedError) {
          } else {
          }

          invitationResults.push({
            email,
            success: false,
            error: errorMessage,
          });
          return null;
        }
      });

      // Create all users in parallel
      await Promise.all(createUserPromises);
      const successCount = invitationResults.filter(
        result => result.success
      ).length;
      const failedCount = validEmails.length - successCount;

      // Show results
      if (successCount > 0 && failedCount === 0) {
        notifications.show(
          `Successfully sent ${successCount} invitation${successCount > 1 ? 's' : ''}!`,
          { severity: 'success' }
        );
      } else if (successCount > 0 && failedCount > 0) {
        // Show cleaner error message for mixed results
        const failedEmails = invitationResults
          .filter(result => !result.success)
          .map(result => result.email);

        const errorTypes = invitationResults
          .filter(result => !result.success)
          .map(result => result.error)
          .filter((error, index, arr) => arr.indexOf(error) === index); // Get unique errors

        let errorSummary = '';
        if (errorTypes.length === 1 && errorTypes[0]?.includes('rate limit')) {
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
        // Show cleaner error message for all failed
        const failedEmails = invitationResults
          .filter(result => !result.success)
          .map(result => result.email);

        const errorTypes = invitationResults
          .filter(result => !result.success)
          .map(result => result.error)
          .filter((error, index, arr) => arr.indexOf(error) === index); // Get unique errors

        let errorMessage = '';
        if (errorTypes.length === 1 && errorTypes[0]?.includes('rate limit')) {
          // Extract the full rate limit message which is user-friendly
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

      // Reset form only if some invitations succeeded
      if (successCount > 0) {
        setFormData({ invites: [{ email: '' }] });
        setErrors({});

        // Notify parent component
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

  const handleEmailChange = (index: number, value: string) => {
    const updatedInvites = [...formData.invites];
    updatedInvites[index] = { email: value };
    setFormData({ invites: updatedInvites });

    // Clear error when user types
    if (errors[index]) {
      const newErrors = { ...errors };
      delete newErrors[index];
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
      invites: [...formData.invites, { email: '' }],
    });
  };

  const removeEmailField = (index: number) => {
    const updatedInvites = [...formData.invites];
    updatedInvites.splice(index, 1);
    setFormData({ invites: updatedInvites });

    // Remove error for this field if it exists
    if (errors[index]) {
      const newErrors = { ...errors };
      delete newErrors[index];
      setErrors(newErrors);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {/* Header Section */}
      <Box mb={3}>
        <Typography variant="h6" component="h2" gutterBottom>
          Invite Team Members
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Send invitations to colleagues to join your organization. You can
          invite up to {MAX_TEAM_MEMBERS} members at once.
        </Typography>
      </Box>

      {/* Form Fields */}
      <Stack spacing={2} sx={{ mb: 3 }}>
        {formData.invites.map((invite, index) => {
          // Create stable key from email or index
          const inviteKey = invite.email || `invite-${index}`;
          return (
            <Box key={inviteKey} display="flex" alignItems="flex-start" gap={2}>
              <TextField
                fullWidth
                label="Email Address"
                value={invite.email}
                onChange={e => handleEmailChange(index, e.target.value)}
                error={Boolean(errors[index]?.hasError)}
                helperText={errors[index]?.message || ''}
                placeholder="colleague@company.com"
                variant="outlined"
                size="small"
                data-tour={index === 0 ? 'invite-email-input' : undefined}
              />
              {formData.invites.length > 1 && (
                <IconButton
                  onClick={() => removeEmailField(index)}
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

      {/* Submit Button */}
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
    </Box>
  );
}
