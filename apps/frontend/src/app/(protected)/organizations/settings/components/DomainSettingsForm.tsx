'use client';

import React, { useState } from 'react';
import {
  Box,
  TextField,
  Button,
  Alert,
  CircularProgress,
  Grid,
  Chip,
  Typography,
} from '@mui/material';
import {
  Save as SaveIcon,
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
} from '@mui/icons-material';
import { Organization } from '@/utils/api-client/interfaces/organization';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useNotifications } from '@/components/common/NotificationContext';

interface DomainSettingsFormProps {
  organization: Organization;
  sessionToken: string;
  onUpdate: () => void;
}

export default function DomainSettingsForm({
  organization,
  sessionToken,
  onUpdate,
}: DomainSettingsFormProps) {
  const notifications = useNotifications();
  const [formData, setFormData] = useState({
    domain: organization.domain || '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleChange =
    (field: keyof typeof formData) =>
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setFormData({ ...formData, [field]: e.target.value });
      setError(null);
    };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const apiFactory = new ApiClientFactory(sessionToken);
      const organizationsClient = apiFactory.getOrganizationsClient();

      await organizationsClient.updateOrganization(organization.id, {
        domain: formData.domain || undefined,
      });

      notifications.show('Domain settings updated successfully', {
        severity: 'success',
      });
      onUpdate();
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : 'Failed to update domain settings'
      );
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
        <Grid size={12}>
          <Box sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              Domain verification status:
            </Typography>
            {organization.is_domain_verified ? (
              <Chip
                icon={<CheckCircleIcon />}
                label="Verified"
                color="success"
                size="small"
              />
            ) : (
              <Chip
                icon={<CancelIcon />}
                label="Not Verified"
                color="default"
                size="small"
              />
            )}
          </Box>
        </Grid>

        <Grid size={12}>
          <TextField
            fullWidth
            label="Domain"
            value={formData.domain}
            onChange={handleChange('domain')}
            placeholder="example.com"
            helperText="Your organization's domain for automatic user association"
          />
        </Grid>

        {!organization.is_domain_verified && formData.domain && (
          <Grid size={12}>
            <Alert severity="info">
              After saving your domain, you&apos;ll need to verify ownership to
              enable automatic user association. Contact support for
              verification instructions.
            </Alert>
          </Grid>
        )}

        <Grid size={12}>
          <Button
            type="submit"
            variant="contained"
            startIcon={saving ? <CircularProgress size={20} /> : <SaveIcon />}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </Grid>
      </Grid>
    </Box>
  );
}
