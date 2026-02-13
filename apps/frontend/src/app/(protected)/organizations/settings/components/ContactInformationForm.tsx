'use client';

import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Grid,
} from '@mui/material';
import { Save as SaveIcon } from '@mui/icons-material';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { validateEmail, validatePhone } from '@/utils/validation';
import { useFormChangeDetection } from '@/hooks/useFormChangeDetection';

interface ContactInformationFormProps {
  organization: Organization;
  sessionToken: string;
  onUpdate: () => void;
}

export default function ContactInformationForm({
  organization,
  sessionToken,
  onUpdate,
}: ContactInformationFormProps) {
  const notifications = useNotifications();
  const [formData, setFormData] = useState({
    email: organization.email || '',
    phone: organization.phone || '',
    address: organization.address || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const { hasChanges, resetChanges } = useFormChangeDetection({
    initialData: {
      email: organization.email || '',
      phone: organization.phone || '',
      address: organization.address || '',
    },
    currentData: formData,
  });

  const handleChange =
    (field: keyof typeof formData) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData({ ...formData, [field]: e.target.value });
      setError(null);
      // Clear field error on change
      if (fieldErrors[field]) {
        setFieldErrors({ ...fieldErrors, [field]: '' });
      }
    };

  const handleBlur = (field: 'email' | 'phone') => () => {
    const value = formData[field];
    if (value) {
      const validation =
        field === 'email' ? validateEmail(value) : validatePhone(value);
      if (!validation.isValid) {
        setFieldErrors({ ...fieldErrors, [field]: validation.message || '' });
      }
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    if (!hasChanges) {
      setSaving(false);
      return;
    }

    // Validate email and phone before submitting
    const errors: Record<string, string> = {};

    if (formData.email) {
      const emailValidation = validateEmail(formData.email);
      if (!emailValidation.isValid) {
        errors.email = emailValidation.message || '';
      }
    }

    if (formData.phone) {
      const phoneValidation = validatePhone(formData.phone);
      if (!phoneValidation.isValid) {
        errors.phone = phoneValidation.message || '';
      }
    }

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      setSaving(false);
      return;
    }

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const organizationsClient = apiFactory.getOrganizationsClient();

      await organizationsClient.updateOrganization(organization.id, {
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        address: formData.address || undefined,
      });

      notifications.show('Contact information updated successfully', {
        severity: 'success',
      });
      resetChanges();
      onUpdate();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update contact information');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}
      <Grid container spacing={3}>
        <Grid
          size={{
            xs: 12,
            md: 6,
          }}
        >
          <TextField
            fullWidth
            label="Email"
            value={formData.email}
            onChange={handleChange('email')}
            onBlur={handleBlur('email')}
            placeholder="contact@example.com"
            error={!!fieldErrors.email}
            helperText={
              fieldErrors.email || 'Primary contact email for your organization'
            }
          />
        </Grid>

        <Grid
          size={{
            xs: 12,
            md: 6,
          }}
        >
          <TextField
            fullWidth
            label="Phone"
            value={formData.phone}
            onChange={handleChange('phone')}
            onBlur={handleBlur('phone')}
            placeholder="+1 (555) 123-4567"
            error={!!fieldErrors.phone}
            helperText={fieldErrors.phone || 'Primary contact phone number'}
          />
        </Grid>

        <Grid size={12}>
          <TextField
            fullWidth
            label="Address"
            value={formData.address}
            onChange={handleChange('address')}
            multiline
            rows={3}
            placeholder="123 Main St, City, State, ZIP"
            helperText="Physical address of your organization"
          />
        </Grid>

        <Grid size={12}>
          <Button
            type="submit"
            variant="contained"
            startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
            disabled={saving || !hasChanges}
            sx={{
              '&.Mui-disabled': {
                backgroundColor: 'action.disabledBackground',
                color: 'action.disabled',
              },
            }}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
