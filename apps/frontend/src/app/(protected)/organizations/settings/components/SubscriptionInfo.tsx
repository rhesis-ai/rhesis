'use client';

import React from 'react';
import { Box, Grid, Typography, Chip, Alert } from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Cancel as CancelIcon,
  People as PeopleIcon,
  Event as EventIcon,
} from '@mui/icons-material';
import { Organization } from '@/utils/api-client/interfaces/organization';

interface SubscriptionInfoProps {
  organization: Organization;
}

export default function SubscriptionInfo({
  organization,
}: SubscriptionInfoProps) {
  const formatDate = (dateString: string | undefined) => {
    if (!dateString) return 'Not set';
    try {
      return new Date(dateString).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch {
      return 'Invalid date';
    }
  };

  const isExpired = organization.subscription_ends_at
    ? new Date(organization.subscription_ends_at) < new Date()
    : false;

  const daysUntilExpiration = organization.subscription_ends_at
    ? Math.ceil(
        (new Date(organization.subscription_ends_at).getTime() -
          new Date().getTime()) /
          (1000 * 60 * 60 * 24)
      )
    : null;

  return (
    <Box>
      <Grid container spacing={3}>
        {/* Active Status */}
        <Grid
          size={{
            xs: 12,
            md: 6,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              Organization Status:
            </Typography>
          </Box>
          {organization.is_active ? (
            <Chip
              icon={<CheckCircleIcon />}
              label="Active"
              color="success"
              size="small"
            />
          ) : (
            <Chip
              icon={<CancelIcon />}
              label="Inactive"
              color="error"
              size="small"
            />
          )}
        </Grid>

        {/* Max Users */}
        <Grid
          size={{
            xs: 12,
            md: 6,
          }}
        >
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <PeopleIcon fontSize="small" color="action" />
            <Typography variant="body2" color="text.secondary">
              Maximum Users:
            </Typography>
          </Box>
          <Typography variant="body1">
            {organization.max_users ? organization.max_users : 'Unlimited'}
          </Typography>
        </Grid>

        {/* Subscription End Date */}
        <Grid size={12}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <EventIcon fontSize="small" color="action" />
            <Typography variant="body2" color="text.secondary">
              Subscription Ends:
            </Typography>
          </Box>
          <Typography variant="body1">
            {formatDate(organization.subscription_ends_at)}
          </Typography>

          {organization.subscription_ends_at && (
            <Box sx={{ mt: 2 }}>
              {isExpired ? (
                <Alert severity="error">
                  Your subscription has expired. Please contact support to
                  renew.
                </Alert>
              ) : daysUntilExpiration !== null && daysUntilExpiration <= 30 ? (
                <Alert severity="warning">
                  Your subscription will expire in {daysUntilExpiration} day
                  {daysUntilExpiration !== 1 ? 's' : ''}. Please contact support
                  to renew.
                </Alert>
              ) : (
                <Alert severity="info">
                  Your subscription is active and will renew automatically.
                </Alert>
              )}
            </Box>
          )}
        </Grid>

        {/* Organization Created Date */}
        <Grid size={12}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
            <EventIcon fontSize="small" color="action" />
            <Typography variant="body2" color="text.secondary">
              Organization Created:
            </Typography>
          </Box>
          <Typography variant="body1">
            {formatDate(organization.createdAt)}
          </Typography>
        </Grid>

        <Grid size={12}>
          <Alert severity="info">
            To modify subscription details or user limits, please contact your
            account manager or support team.
          </Alert>
        </Grid>
      </Grid>
    </Box>
  );
}
