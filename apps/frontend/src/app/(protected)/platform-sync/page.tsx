'use client';

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  CircularProgress,
  Divider,
  FormControlLabel,
  FormGroup,
  Paper,
  Stack,
  TextField,
  Typography,
} from '@mui/material';
import { useSession } from 'next-auth/react';
import { PageLayout } from '@/components/layout/PageLayout';
import { CloudSyncIcon } from '@/components/icons';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';
import { useNotifications } from '@/components/common/NotificationContext';
import { isAuthenticated } from '@/hooks/useIsAuthenticated';
import type {
  PlatformSyncResource,
  PlatformSyncSummary,
} from '@/utils/api-client/interfaces/platform-sync';

const DEFAULT_BASE_URL = 'https://api.rhesis.ai';
const DEFAULT_SELECTED = ['models', 'endpoints'];

const IS_LOCAL =
  process.env.NEXT_PUBLIC_FRONTEND_ENV?.toLowerCase() === 'local';

export default function PlatformSyncPage() {
  const { status } = useSession();
  const { allowed: canCreate, loading: permsLoading } = useCanWithStatus(
    Capability.Model.CREATE
  );
  const notifications = useNotifications();

  const [resources, setResources] = useState<PlatformSyncResource[]>([]);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [apiKey, setApiKey] = useState('');
  const [baseUrl, setBaseUrl] = useState(DEFAULT_BASE_URL);
  const [selected, setSelected] = useState<Set<string>>(
    new Set(DEFAULT_SELECTED)
  );
  const [syncing, setSyncing] = useState(false);
  const [summary, setSummary] = useState<PlatformSyncSummary | null>(null);

  const loadResources = useCallback(async () => {
    try {
      setResourcesLoading(true);
      const client = new ApiClientFactory().getPlatformSyncClient();
      setResources(await client.getResources());
    } catch (err) {
      notifications.show(
        err instanceof Error ? err.message : 'Failed to load sync options',
        { severity: 'error' }
      );
    } finally {
      setResourcesLoading(false);
    }
  }, [notifications]);

  useEffect(() => {
    if (IS_LOCAL && isAuthenticated(status) && canCreate) {
      loadResources();
    }
  }, [status, canCreate, loadResources]);

  const toggleResource = (key: string) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleSync = useCallback(async () => {
    if (!apiKey.trim()) {
      notifications.show('Enter a Rhesis API key', { severity: 'warning' });
      return;
    }
    if (selected.size === 0) {
      notifications.show('Select at least one resource to sync', {
        severity: 'warning',
      });
      return;
    }
    try {
      setSyncing(true);
      setSummary(null);
      const client = new ApiClientFactory().getPlatformSyncClient();
      const result = await client.sync({
        api_key: apiKey.trim(),
        base_url: baseUrl.trim() || DEFAULT_BASE_URL,
        resources: Array.from(selected),
      });
      setSummary(result);
      notifications.show('Sync complete', { severity: 'success' });
    } catch (err) {
      notifications.show(err instanceof Error ? err.message : 'Sync failed', {
        severity: 'error',
      });
    } finally {
      setSyncing(false);
    }
  }, [apiKey, baseUrl, selected, notifications]);

  if (!IS_LOCAL) {
    return (
      <PageLayout title="Platform Sync">
        <Alert severity="info">
          Platform Sync is only available in local development deployments.
        </Alert>
      </PageLayout>
    );
  }

  if (permsLoading) {
    return <PageLoadingState />;
  }

  if (!canCreate) {
    return <AccessDenied resource="platform sync" />;
  }

  return (
    <PageLayout
      title="Platform Sync"
      description="Pull models, endpoints and other configuration from the Rhesis platform into this local deployment. Paste an API key, choose what to sync, and run it. Secrets (provider keys, endpoint auth) are never returned by the platform — those fields are left blank and reported below so you can fill them in."
    >
      <Box sx={{ maxWidth: 720 }}>
        <Paper variant="outlined" sx={{ p: 3 }}>
          <Stack spacing={3}>
            <TextField
              label="Rhesis API key"
              placeholder="rh-..."
              type="password"
              value={apiKey}
              onChange={e => setApiKey(e.target.value)}
              fullWidth
              autoComplete="off"
              helperText="Create one under API in the platform sidebar. Used only for this request; never stored."
            />

            <TextField
              label="Platform URL"
              value={baseUrl}
              onChange={e => setBaseUrl(e.target.value)}
              fullWidth
            />

            <Box>
              <Typography variant="subtitle2" gutterBottom>
                What to sync
              </Typography>
              {resourcesLoading ? (
                <CircularProgress size={20} />
              ) : (
                <FormGroup>
                  {resources.map(resource => (
                    <FormControlLabel
                      key={resource.key}
                      control={
                        <Checkbox
                          checked={selected.has(resource.key)}
                          onChange={() => toggleResource(resource.key)}
                        />
                      }
                      label={
                        <Box>
                          <Typography variant="body2">
                            {resource.label}
                            {resource.dependencies.length > 0 && (
                              <Typography
                                component="span"
                                variant="caption"
                                sx={{ color: 'text.secondary', ml: 1 }}
                              >
                                (also pulls: {resource.dependencies.join(', ')})
                              </Typography>
                            )}
                          </Typography>
                          {resource.description && (
                            <Typography
                              variant="caption"
                              sx={{ color: 'text.secondary' }}
                            >
                              {resource.description}
                            </Typography>
                          )}
                        </Box>
                      }
                    />
                  ))}
                </FormGroup>
              )}
            </Box>

            <Box>
              <Button
                variant="contained"
                startIcon={
                  syncing ? (
                    <CircularProgress size={16} color="inherit" />
                  ) : (
                    <CloudSyncIcon />
                  )
                }
                onClick={handleSync}
                disabled={syncing || resourcesLoading}
              >
                {syncing ? 'Syncing…' : 'Sync'}
              </Button>
            </Box>
          </Stack>
        </Paper>

        {summary && <SyncSummaryView summary={summary} />}
      </Box>
    </PageLayout>
  );
}

function SyncSummaryView({ summary }: { summary: PlatformSyncSummary }) {
  return (
    <Paper variant="outlined" sx={{ p: 3, mt: 3 }}>
      <Typography variant="h6" gutterBottom>
        Result
      </Typography>
      {summary.source_user_email && (
        <Typography variant="body2" sx={{ color: 'text.secondary', mb: 2 }}>
          Synced from {summary.source_user_email} at {summary.base_url}
        </Typography>
      )}

      <Stack spacing={1}>
        {summary.results.map(result => (
          <Box
            key={result.resource}
            sx={{ display: 'flex', alignItems: 'center', gap: 1 }}
          >
            <Typography variant="body2" sx={{ minWidth: 120 }}>
              {result.label}
            </Typography>
            <Chip
              size="small"
              label={`${result.created} created`}
              color={result.created > 0 ? 'success' : 'default'}
              variant="outlined"
            />
            <Chip
              size="small"
              label={`${result.skipped} skipped`}
              variant="outlined"
            />
            {result.errors.length > 0 && (
              <Chip
                size="small"
                color="error"
                variant="outlined"
                label={result.errors.join('; ')}
              />
            )}
          </Box>
        ))}
      </Stack>

      {summary.gaps.length > 0 && (
        <>
          <Divider sx={{ my: 2 }} />
          <Alert severity="warning" sx={{ mb: 1 }}>
            The platform never returns secrets, so these were left blank — set
            them locally to finish authenticating.
          </Alert>
          <Stack spacing={0.5}>
            {summary.gaps.map((gap, index) => (
              <Typography
                // eslint-disable-next-line react/no-array-index-key -- display-only list, stable order
                key={`${gap.resource}-${gap.name}-${gap.field}-${index}`}
                variant="body2"
                sx={{ color: 'text.secondary' }}
              >
                <strong>{gap.name}</strong> ({gap.resource}) — missing{' '}
                {gap.field}
              </Typography>
            ))}
          </Stack>
        </>
      )}
    </Paper>
  );
}
