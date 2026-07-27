'use client';

import * as React from 'react';
import { safeRandomUUID } from '@/utils/uuid';
import {
  Box,
  TextField,
  IconButton,
  Snackbar,
  Alert,
  Stack,
  Link,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useState } from 'react';
import OnboardingStepHeader from './OnboardingStepHeader';
import OnboardingNavButtons from './OnboardingNavButtons';
import { ONBOARDING_STEPS } from './onboarding-steps';

interface FormData {
  invites: { id: string; email: string }[];
}

interface InviteTeamStepProps {
  formData: FormData;
  updateFormData: (data: Partial<FormData>) => void;
  onNext: () => void;
  onBack: () => void;
}

const MAX_TEAM_MEMBERS = 10;
const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function InviteTeamStep({
  formData,
  updateFormData,
  onNext,
  onBack,
}: InviteTeamStepProps) {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [errors, setErrors] = useState<{
    [key: number]: { hasError: boolean; message: string };
  }>({});

  const step = ONBOARDING_STEPS[1];

  const nonEmptyInvites = formData.invites.filter(invite =>
    invite.email.trim()
  );
  const hasFilledEmails = nonEmptyInvites.length > 0;
  const primaryLabel = hasFilledEmails ? 'Next' : 'Skip';

  const validateForm = () => {
    const newErrors: { [key: number]: { hasError: boolean; message: string } } =
      {};
    let hasError = false;

    if (nonEmptyInvites.length > MAX_TEAM_MEMBERS) {
      setErrorMessage(
        `You can invite a maximum of ${MAX_TEAM_MEMBERS} team members during onboarding.`
      );
      return false;
    }

    const emailsToCheck = formData.invites
      .map((invite, index) => ({
        email: invite.email.trim().toLowerCase(),
        index,
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

    formData.invites.forEach((invite, index) => {
      const trimmedEmail = invite.email.trim();

      if (trimmedEmail) {
        if (!emailRegex.test(trimmedEmail)) {
          newErrors[index] = {
            hasError: true,
            message: 'Please enter a valid email address',
          };
          hasError = true;
        } else if (duplicateEmails.has(trimmedEmail.toLowerCase())) {
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

    if (hasFilledEmails && !validateForm()) {
      return;
    }

    try {
      setIsSubmitting(true);
      onNext();
    } catch {
      setErrorMessage('Failed to submit form. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEmailChange = (index: number, value: string) => {
    const updatedInvites = [...formData.invites];
    updatedInvites[index] = { ...updatedInvites[index], email: value };
    updateFormData({ invites: updatedInvites });

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
      invites: [...formData.invites, { id: safeRandomUUID(), email: '' }],
    });
  };

  const removeEmailField = (index: number) => {
    const updatedInvites = [...formData.invites];
    updatedInvites.splice(index, 1);
    updateFormData({ invites: updatedInvites });

    if (errors[index]) {
      const newErrors = { ...errors };
      delete newErrors[index];
      setErrors(newErrors);
    }
  };

  return (
    <Box
      component="form"
      onSubmit={handleSubmit}
      sx={{
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        gap: '50px',
      }}
    >
      <OnboardingStepHeader
        title={step.contentTitle}
        description={step.contentDescription}
      />

      <Stack spacing={3.75} sx={{ width: '100%' }}>
        {formData.invites.map((invite, index) => {
          const hasValue = invite.email.trim().length > 0;

          return (
            <Box key={invite.id} display="flex" alignItems="center" gap={1.25}>
              <TextField
                fullWidth
                label="Email Address"
                InputLabelProps={{ shrink: hasValue }}
                value={invite.email}
                onChange={e => handleEmailChange(index, e.target.value)}
                error={Boolean(errors[index]?.hasError)}
                helperText={errors[index]?.message || ''}
                variant="outlined"
              />
              {formData.invites.length > 1 && (
                <IconButton
                  onClick={() => removeEmailField(index)}
                  aria-label="Remove email"
                  sx={{ flexShrink: 0, color: 'greyscale.subtitle' }}
                >
                  <DeleteOutlineIcon />
                </IconButton>
              )}
            </Box>
          );
        })}

        <Link
          component="button"
          type="button"
          onClick={addEmailField}
          underline="none"
          sx={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: 0.5,
            color: 'primary.main',
            fontSize: 16,
            lineHeight: '24px',
            cursor:
              formData.invites.length >= MAX_TEAM_MEMBERS
                ? 'not-allowed'
                : 'pointer',
            opacity: formData.invites.length >= MAX_TEAM_MEMBERS ? 0.5 : 1,
            alignSelf: 'flex-start',
          }}
          disabled={formData.invites.length >= MAX_TEAM_MEMBERS}
        >
          <AddIcon sx={{ fontSize: 24 }} />
          Add another email
        </Link>
      </Stack>

      <OnboardingNavButtons
        onBack={onBack}
        primaryLabel={isSubmitting ? 'Saving...' : primaryLabel}
        primaryType="submit"
        isSubmitting={isSubmitting}
        onPrimary={() => undefined}
      />

      <Snackbar
        open={!!errorMessage}
        autoHideDuration={6000}
        onClose={() => setErrorMessage(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setErrorMessage(null)} severity="error">
          {errorMessage}
        </Alert>
      </Snackbar>
    </Box>
  );
}
