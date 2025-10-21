'use client';

import React, { useState, useEffect } from 'react';
import {
  Box,
  Card,
  CardContent,
  Switch,
  Typography,
  Alert,
  Link,
  CircularProgress,
  Snackbar,
  FormControlLabel,
} from '@mui/material';
import { Info as InfoIcon } from '@mui/icons-material';
import { useNotifications } from '@/contexts/NotificationContext';
import { setTelemetryEnabled } from '@/lib/telemetry';

interface TelemetrySettingsProps {
  sessionToken: string;
}

export default function TelemetrySettings({ sessionToken }: TelemetrySettingsProps) {
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(false);
  const notifications = useNotifications();

  // Fetch current telemetry status on mount
  useEffect(() => {
    fetchTelemetryStatus();
  }, []);

  const fetchTelemetryStatus = async () => {
    try {
      const response = await fetch('/api/users/telemetry/status', {
        headers: {
          Authorization: `Bearer ${sessionToken}`,
        },
      });

      if (!response.ok) {
        throw new Error('Failed to fetch telemetry status');
      }

      const data = await response.json();
      setEnabled(data.telemetry_enabled);
      
      // Update telemetry SDK
      setTelemetryEnabled(data.telemetry_enabled);
    } catch (error) {
      console.error('Error fetching telemetry status:', error);
      notifications.showError('Failed to load telemetry settings');
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = event.target.checked;
    setUpdating(true);

    try {
      const endpoint = newValue
        ? '/api/users/telemetry/enable'
        : '/api/users/telemetry/disable';

      const response = await fetch(endpoint, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${sessionToken}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Failed to update telemetry settings');
      }

      const data = await response.json();
      setEnabled(newValue);
      
      // Update telemetry SDK
      setTelemetryEnabled(newValue);
      
      notifications.showSuccess(data.message || 'Telemetry settings updated');
    } catch (error) {
      console.error('Error updating telemetry settings:', error);
      notifications.showError('Failed to update telemetry settings');
    } finally {
      setUpdating(false);
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" p={4}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Card>
      <CardContent>
        <Box display="flex" flexDirection="column" gap={2}>
          <Typography variant="h6" gutterBottom>
            Anonymous Usage Data
          </Typography>

          <Alert severity="info" icon={<InfoIcon />}>
            Help us improve Rhesis by sharing anonymous usage data. No personally
            identifiable information (PII) is collected.
          </Alert>

          <FormControlLabel
            control={
              <Switch
                checked={enabled}
                onChange={handleToggle}
                disabled={updating}
                color="primary"
              />
            }
            label={
              <Box>
                <Typography variant="body1">
                  Share anonymous usage data
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {enabled
                    ? 'Thank you for helping improve Rhesis!'
                    : 'Currently disabled'}
                </Typography>
              </Box>
            }
          />

          <Box>
            <Typography variant="body2" color="text.secondary" gutterBottom>
              <strong>What we collect:</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary" component="ul">
              <li>Feature usage (which features are used and how often)</li>
              <li>API endpoint usage statistics</li>
              <li>Page views and navigation patterns</li>
              <li>Performance metrics (response times)</li>
              <li>Error rates</li>
            </Typography>

            <Typography variant="body2" color="text.secondary" gutterBottom sx={{ mt: 2 }}>
              <strong>What we DON'T collect:</strong>
            </Typography>
            <Typography variant="body2" color="text.secondary" component="ul">
              <li>Email addresses or names</li>
              <li>Test data or prompts</li>
              <li>API keys or tokens</li>
              <li>IP addresses</li>
              <li>Any personally identifiable information (PII)</li>
            </Typography>

            <Typography variant="body2" sx={{ mt: 2 }}>
              <Link
                href="https://docs.rhesis.ai/privacy"
                target="_blank"
                rel="noopener noreferrer"
              >
                Learn more about our privacy practices →
              </Link>
            </Typography>
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
}

