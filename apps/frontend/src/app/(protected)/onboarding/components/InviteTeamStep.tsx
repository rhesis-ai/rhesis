import * as React from 'react';
import {
  Box,
  TextField,
  Button,
  IconButton,
  CircularProgress,
  Snackbar,
  Alert,
  Stack,
  Paper,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteIcon from '@mui/icons-material/Delete';
import { useState } from 'react';
import StepHeader from './StepHeader';

interface FormData {
  invites: { id: string; email: string }[];
}

interface InviteTeamStepProps {
  formData: FormData;
  updateFormData: (data: Partial<FormData>) => void;
  onNext: () => void;
  onBack: () => void;
}

export default function InviteTeamStep({
  formData,
  updateFormData,
  onNext,
  onBack,
}: InviteTeamStepProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
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
      setErrorMessage(
        `You can invite a maximum of ${MAX_TEAM_MEMBERS} team members during onboarding.`
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

    try {
      setIsSubmitting(true);

      // Proceed to next step
      onNext();
    } catch (_error) {
      setErrorMessage('Failed to submit form. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEmailChange = (index: number, value: string) => {
    const updatedInvites = [...formData.invites];
    updatedInvites[index] = { ...updatedInvites[index], email: value };
    updateFormData({ invites: updatedInvites });

    // Clear error when user types
    if (errors[index]) {
      const newErrors = { ...errors };
      delete newErrors[index];
      setErrors(newErrors);
    }
  };

  const addEmailField = () => {
    if (formData.invites.length >= MAX_TEAM_MEMBERS) {
      setErrorMessage(
        `You can invite a maximum of ${MAX_TEAM_MEMBERS} team members during onboarding.`
      );
      return;
    }

    updateFormData({
      invites: [...formData.invites, { id: crypto.randomUUID(), email: '' }],
    });
  };

  const removeEmailField = (index: number) => {
    const updatedInvites = [...formData.invites];
    updatedInvites.splice(index, 1);
    updateFormData({ invites: updatedInvites });

    // Remove error for this field if it exists
    if (errors[index]) {
      const newErrors = { ...errors };
      delete newErrors[index];
      setErrors(newErrors);
    }
  };

  const handleCloseSnackbar = () => {
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      <StepHeader
        title="Invite Team Members"
        description="Invite colleagues to join your organization. You can skip this step and add team members later."
        subtitle={`You can invite up to ${MAX_TEAM_MEMBERS} team members during onboarding.`}
      />

      {/* Form Fields */}
      <Paper variant="outlined" elevation={0}>
        <Box p={3}>
          <Stack spacing={3}>
            {formData.invites.map((invite, index) => (
              <Box
                key={invite.id}
                display="flex"
                alignItems="flex-start"
                gap={2}
              >
                <TextField
                  fullWidth
                  label="Email Address"
                  value={invite.email}
                  onChange={e => handleEmailChange(index, e.target.value)}
                  error={Boolean(errors[index]?.hasError)}
                  helperText={errors[index]?.message || ''}
                  placeholder="colleague@company.com"
                  variant="outlined"
                />
                {formData.invites.length > 1 && (
                  <IconButton
                    onClick={() => removeEmailField(index)}
                    color="error"
                    size="large"
                  >
                    <DeleteIcon />
                  </IconButton>
                )}
              </Box>
            ))}

            <Box display="flex" justifyContent="flex-start">
              <Button
                startIcon={<AddIcon />}
                onClick={addEmailField}
                variant="outlined"
                size="medium"
                disabled={formData.invites.length >= MAX_TEAM_MEMBERS}
              >
                {formData.invites.length >= MAX_TEAM_MEMBERS
                  ? `Maximum ${MAX_TEAM_MEMBERS} invites reached`
                  : 'Add Another Email'}
              </Button>
            </Box>
          </Stack>
        </Box>
      </Paper>

      {/* Action Buttons */}
      <Box display="flex" justifyContent="space-between" mt={4}>
        <Button onClick={onBack} disabled={isSubmitting} size="large">
          Back
        </Button>
        <Button
          type="submit"
          variant="contained"
          color="primary"
          disabled={isSubmitting}
          startIcon={
            isSubmitting ? <CircularProgress size={20} color="inherit" /> : null
          }
          size="large"
        >
          {isSubmitting ? 'Saving...' : 'Next'}
        </Button>
      </Box>

      {/* Notifications */}
      <Snackbar
        open={!!errorMessage}
        autoHideDuration={6000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity="error">
          {errorMessage}
        </Alert>
      </Snackbar>

      <Snackbar
        open={!!successMessage}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={handleCloseSnackbar} severity="success">
          {successMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}
