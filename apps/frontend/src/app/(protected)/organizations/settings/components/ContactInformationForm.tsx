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
        email: formData.email || undefined,
        phone: formData.phone || undefined,
        address: formData.address || undefined,
      });

      notifications.show('Contact information updated successfully', {
        severity: 'success',
      });
      onUpdate();
    } catch (err: any) {
      console.error('Error updating contact information:', err);
      setError(err.message || 'Failed to update contact information');
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
        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Email"
            value={formData.email}
            onChange={handleChange('email')}
            type="email"
            placeholder="contact@example.com"
            helperText="Primary contact email for your organization"
          />
        </Grid>

        <Grid item xs={12} md={6}>
          <TextField
            fullWidth
            label="Phone"
            value={formData.phone}
            onChange={handleChange('phone')}
            type="tel"
            placeholder="+1 (555) 123-4567"
            helperText="Primary contact phone number"
          />
        </Grid>

        <Grid item xs={12}>
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

        <Grid item xs={12}>
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
