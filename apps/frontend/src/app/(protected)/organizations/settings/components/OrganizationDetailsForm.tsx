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
import { useRouter } from 'next/navigation';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';
import { validateUrl, normalizeUrl } from '@/utils/validation';
import { useFormChangeDetection } from '@/hooks/useFormChangeDetection';

interface OrganizationDetailsFormProps {
  organization: Organization;
  sessionToken: string;
  onUpdate: () => void;
}

export default function OrganizationDetailsForm({
  organization,
  sessionToken,
  onUpdate,
}: OrganizationDetailsFormProps) {
  const router = useRouter();
  const notifications = useNotifications();
  const [formData, setFormData] = useState({
    name: organization.name || '',
    display_name: organization.display_name || '',
    description: organization.description || '',
    website: organization.website || '',
    logo_url: organization.logo_url || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  const { hasChanges, resetChanges } = useFormChangeDetection({
    initialData: {
      name: organization.name || '',
      display_name: organization.display_name || '',
      description: organization.description || '',
      website: organization.website || '',
      logo_url: organization.logo_url || '',
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

  const handleBlur = (field: 'website' | 'logo_url') => () => {
    const value = formData[field];
    if (value) {
      const validation = validateUrl(value);
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

    // Validate URLs before submitting
    const errors: Record<string, string> = {};

    if (formData.website) {
      const websiteValidation = validateUrl(formData.website);
      if (!websiteValidation.isValid) {
        errors.website = websiteValidation.message || '';
      }
    }

    if (formData.logo_url) {
      const logoValidation = validateUrl(formData.logo_url);
      if (!logoValidation.isValid) {
        errors.logo_url = logoValidation.message || '';
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

      // Normalize URLs before sending
      const website = formData.website
        ? normalizeUrl(formData.website)
        : undefined;
      const logo_url = formData.logo_url
        ? normalizeUrl(formData.logo_url)
        : undefined;

      await organizationsClient.updateOrganization(organization.id, {
        name: formData.name,
        display_name: formData.display_name || undefined,
        description: formData.description || undefined,
        website,
        logo_url,
      });

      notifications.show('Organization details updated successfully', {
        severity: 'success',
      });

      resetChanges();
      // Refresh to update navigation with new organization name
      router.refresh();
      onUpdate();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update organization details');
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
            label="Organization Name"
            value={formData.name}
            onChange={handleChange('name')}
            required
            helperText="The internal name for your organization"
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
            label="Display Name"
            value={formData.display_name}
            onChange={handleChange('display_name')}
            helperText="Friendly name shown to users (optional)"
          />
        </Grid>

        <Grid size={12}>
          <TextField
            fullWidth
            label="Description"
            value={formData.description}
            onChange={handleChange('description')}
            multiline
            rows={3}
            helperText="A brief description of your organization"
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
            label="Website"
            value={formData.website}
            onChange={handleChange('website')}
            onBlur={handleBlur('website')}
            placeholder="https://example.com"
            error={!!fieldErrors.website}
            helperText={fieldErrors.website || "Your organization's website"}
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
            label="Logo URL"
            value={formData.logo_url}
            onChange={handleChange('logo_url')}
            onBlur={handleBlur('logo_url')}
            placeholder="https://example.com/logo.png"
            error={!!fieldErrors.logo_url}
            helperText={
              fieldErrors.logo_url || "URL to your organization's logo"
            }
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
