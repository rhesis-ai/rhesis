'use client';

import * as React from 'react';
import {
  Box,
  TextField,
  CircularProgress,
  Snackbar,
  Alert,
  Stack,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { useEffect, useState } from 'react';
import OnboardingStepHeader from './OnboardingStepHeader';
import OnboardingNavButtons from './OnboardingNavButtons';
import { ONBOARDING_STEPS } from './onboarding-steps';
import {
  validateName,
  validateOrganizationName,
  validateProjectName,
  validateUrl,
  normalizeUrl,
} from '@/utils/validation';
import { isSessionLoading } from '@/hooks/useIsAuthenticated';

interface FormData {
  firstName: string;
  lastName: string;
  organizationName: string;
  projectName: string;
  website: string;
}

interface ExtendedUser {
  given_name?: string;
  family_name?: string;
  name?: string | null;
  email?: string | null;
}

interface OrganizationDetailsStepProps {
  formData: FormData;
  updateFormData: (data: Partial<FormData>) => void;
  onNext: () => void;
}

export default function OrganizationDetailsStep({
  formData,
  updateFormData,
  onNext,
}: OrganizationDetailsStepProps) {
  const { data: session, status: sessionStatus } = useSession();
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [hasAttemptedPrefill, setHasAttemptedPrefill] = useState(false);
  const [errors, setErrors] = useState({
    firstName: '',
    lastName: '',
    organizationName: '',
    projectName: '',
    website: '',
  });

  const step = ONBOARDING_STEPS[0];

  useEffect(() => {
    if (isSessionLoading(sessionStatus)) return;

    if (session?.user && !hasAttemptedPrefill) {
      try {
        const data: Partial<FormData> = {};
        const extendedUser = session.user as unknown as ExtendedUser;

        const looksLikeEmail = (str: string): boolean => {
          return str.includes('@') && str.includes('.');
        };

        if (!formData.firstName) {
          if (extendedUser.given_name) {
            data.firstName = extendedUser.given_name;
          } else if (session.user.name && !looksLikeEmail(session.user.name)) {
            const nameParts = session.user.name.split(' ');
            if (nameParts.length > 0) {
              data.firstName = nameParts[0];
            }
          }
        }

        if (!formData.lastName) {
          if (extendedUser.family_name) {
            data.lastName = extendedUser.family_name;
          } else if (session.user.name && !looksLikeEmail(session.user.name)) {
            const nameParts = session.user.name.split(' ');
            if (nameParts.length > 1) {
              data.lastName = nameParts.slice(1).join(' ');
            }
          }
        }

        if (Object.keys(data).length > 0) {
          updateFormData(data);
        }

        setHasAttemptedPrefill(true);
      } catch {
        setHasAttemptedPrefill(true);
      }
    }

    setLoading(false);
  }, [
    session,
    sessionStatus,
    formData.firstName,
    formData.lastName,
    updateFormData,
    hasAttemptedPrefill,
  ]);

  const validateForm = () => {
    const firstNameValidation = validateName(formData.firstName, 'First name');
    const lastNameValidation = validateName(formData.lastName, 'Last name');
    const organizationNameValidation = validateOrganizationName(
      formData.organizationName
    );
    const projectNameValidation = validateProjectName(formData.projectName);
    const websiteValidation = validateUrl(formData.website, {
      required: false,
    });

    const newErrors = {
      firstName: firstNameValidation.message || '',
      lastName: lastNameValidation.message || '',
      organizationName: organizationNameValidation.message || '',
      projectName: projectNameValidation.message || '',
      website: websiteValidation.message || '',
    };

    setErrors(newErrors);

    return (
      firstNameValidation.isValid &&
      lastNameValidation.isValid &&
      organizationNameValidation.isValid &&
      projectNameValidation.isValid &&
      websiteValidation.isValid
    );
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      setIsSubmitting(true);

      try {
        const userData = {
          firstName: formData.firstName,
          lastName: formData.lastName,
          fullName: `${formData.firstName} ${formData.lastName}`,
          organizationName: formData.organizationName,
          projectName: formData.projectName,
          website: formData.website || '',
        };
        sessionStorage.setItem('onboardingUserData', JSON.stringify(userData));
      } catch {
        // sessionStorage may be unavailable
      }

      onNext();
    } catch {
      setErrorMessage('Failed to submit form. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    updateFormData({ [name]: value });

    if (errors[name as keyof typeof errors]) {
      setErrors(prev => ({ ...prev, [name]: '' }));
    }
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
    const { name, value } = e.target;

    if (name === 'website' && value.trim()) {
      const normalized = normalizeUrl(value);
      if (normalized !== value) {
        updateFormData({ [name]: normalized });
      }
    }
  };

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="400px"
      >
        <CircularProgress />
      </Box>
    );
  }

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
        <TextField
          fullWidth
          label="First Name"
          name="firstName"
          value={formData.firstName}
          onChange={handleChange}
          required
          error={Boolean(errors.firstName)}
          helperText={errors.firstName || ''}
          variant="outlined"
        />

        <TextField
          fullWidth
          label="Last Name"
          name="lastName"
          value={formData.lastName}
          onChange={handleChange}
          required
          error={Boolean(errors.lastName)}
          helperText={errors.lastName || ''}
          variant="outlined"
        />

        <TextField
          fullWidth
          label="Organization Name"
          name="organizationName"
          value={formData.organizationName}
          onChange={handleChange}
          required
          error={Boolean(errors.organizationName)}
          helperText={errors.organizationName || ''}
          variant="outlined"
        />

        <TextField
          fullWidth
          label="Project Name"
          name="projectName"
          value={formData.projectName}
          onChange={handleChange}
          required
          error={Boolean(errors.projectName)}
          helperText={errors.projectName || ''}
          variant="outlined"
        />

        <TextField
          fullWidth
          label="Website URL (optional)"
          name="website"
          value={formData.website}
          onChange={handleChange}
          onBlur={handleBlur}
          placeholder="https://example.com"
          error={Boolean(errors.website)}
          helperText={errors.website || ''}
          variant="outlined"
        />
      </Stack>

      <OnboardingNavButtons
        primaryLabel={isSubmitting ? 'Saving...' : 'Next'}
        primaryType="submit"
        showBack={false}
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
