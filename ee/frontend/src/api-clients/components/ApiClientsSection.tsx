'use client';

/**
 * Top-level "API Clients" section rendered on the organization
 * settings page.
 *
 * Owns the data lifecycle (load / mutate / refresh) and the dialog
 * orchestration (create -> reveal-secret, rotate -> reveal-secret).
 * The presentational pieces -- the list table, the create form,
 * the secret reveal -- are pure children that take callbacks; this
 * keeps every API call funneled through one component so the audit
 * trail in the network tab is easy to follow during debugging.
 */

import * as React from 'react';
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Stack,
  Typography,
} from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { SectionCard } from '@/components/common/SectionCard';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import { RouteIcon } from '@/components/icons';
import { useNotifications } from '@/components/common/NotificationContext';
import { useOrgSettings } from '@/contexts/OrgSettingsContext';
import { ApiClientsClient } from '../api/api-clients-client';
import type {
  AuthClient,
  AuthClientCreated,
  AuthClientCreateRequest,
} from '../types';
import ApiClientsList from './ApiClientsList';
import CreateApiClientDrawer from './CreateApiClientDrawer';
import ClientSecretDisplayDrawer from './ClientSecretDisplayDrawer';

export default function ApiClientsSection() {
  const { organization, sessionToken } = useOrgSettings();
  const notifications = useNotifications();

  const [clients, setClients] = React.useState<AuthClient[]>([]);
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  // The created / rotated row we are revealing the one-shot secret
  // for. `null` means no reveal dialog is open. The reveal dialog
  // is the only place the plaintext secret ever lives in component
  // state, and it is dropped when the user acknowledges.
  const [revealing, setRevealing] = React.useState<AuthClientCreated | null>(
    null
  );
  const [revealTitle, setRevealTitle] = React.useState<string>(
    'Save your client secret'
  );

  // Memoise the client; building it on every render would be
  // harmless but creates extra GC pressure on a list refresh.
  const apiClient = React.useMemo(
    () => new ApiClientsClient(sessionToken),
    [sessionToken]
  );

  const loadClients = React.useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const rows = await apiClient.listClients(organization.id);
      setClients(rows);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to load API clients';
      setLoadError(msg);
    } finally {
      setLoading(false);
    }
  }, [apiClient, organization.id]);

  React.useEffect(() => {
    loadClients();
  }, [loadClients]);

  const handleCreate = async (body: AuthClientCreateRequest) => {
    setCreateError(null);
    try {
      const created = await apiClient.createClient(organization.id, body);
      // Close the create dialog *before* revealing the secret so the
      // operator's focus moves to the more important dialog.
      setCreateOpen(false);
      setRevealTitle('Save your client secret');
      setRevealing(created);
      // Optimistic insert at the top -- the list is sorted desc by
      // created_at on the server, so this is what a refetch would
      // show too. Saves a round trip and feels snappy.
      setClients(prev => [stripSecret(created), ...prev]);
    } catch (err: unknown) {
      // Surface the error inside the create dialog so the user can
      // adjust the form without losing what they typed.
      const msg =
        err instanceof Error ? err.message : 'Failed to create API client';
      setCreateError(msg);
      throw err;
    }
  };

  const handleRotate = async (client: AuthClient) => {
    try {
      const rotated = await apiClient.rotateClient(organization.id, client.id);
      setRevealTitle('Save the new client secret');
      setRevealing(rotated);
      // Update the row in place so the new `token_epoch` is visible
      // immediately. Backend bumps `updated_at` too.
      setClients(prev =>
        prev.map(c => (c.id === rotated.id ? stripSecret(rotated) : c))
      );
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to rotate client secret';
      notifications.show(msg, { severity: 'error', autoHideDuration: 5000 });
    }
  };

  const handleDisable = async (client: AuthClient) => {
    try {
      const updated = await apiClient.disableClient(organization.id, client.id);
      setClients(prev => prev.map(c => (c.id === updated.id ? updated : c)));
      notifications.show('Client disabled', {
        severity: 'success',
        autoHideDuration: 3000,
      });
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to disable client';
      notifications.show(msg, { severity: 'error', autoHideDuration: 5000 });
    }
  };

  const handleEnable = async (client: AuthClient) => {
    try {
      const updated = await apiClient.enableClient(organization.id, client.id);
      setClients(prev => prev.map(c => (c.id === updated.id ? updated : c)));
      notifications.show('Client enabled', {
        severity: 'success',
        autoHideDuration: 3000,
      });
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to enable client';
      notifications.show(msg, { severity: 'error', autoHideDuration: 5000 });
    }
  };

  const handleDelete = async (client: AuthClient) => {
    try {
      await apiClient.deleteClient(organization.id, client.id);
      setClients(prev => prev.filter(c => c.id !== client.id));
      notifications.show('Client deleted', {
        severity: 'success',
        autoHideDuration: 3000,
      });
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : 'Failed to delete client';
      notifications.show(msg, { severity: 'error', autoHideDuration: 5000 });
    }
  };

  const openCreateDrawer = () => {
    setCreateError(null);
    setCreateOpen(true);
  };

  const drawers = (
    <>
      <CreateApiClientDrawer
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onSubmit={handleCreate}
        errorMessage={createError}
      />
      {revealing && (
        <ClientSecretDisplayDrawer
          open={revealing !== null}
          clientId={revealing.client_id}
          clientSecret={revealing.client_secret}
          title={revealTitle}
          onAcknowledge={() => setRevealing(null)}
        />
      )}
    </>
  );

  if (loading) {
    return (
      <SectionCard>
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 3 }}>
          <CircularProgress size={24} />
        </Box>
      </SectionCard>
    );
  }

  if (clients.length === 0) {
    return (
      <>
        <SectionCard>
          <SectionEmptyState
            icon={RouteIcon}
            title="No API clients yet"
            description="API Clients let an external integration trade an OIDC access token from your IdP for a Rhesis access token (RFC 8693). Configure the IdP under Single Sign-On first; clients only work for organizations with SSO enabled and a slug set."
            actionLabel="Create API client"
            onAction={openCreateDrawer}
            showAddIcon
            inset={false}
          />
        </SectionCard>
        {drawers}
      </>
    );
  }

  return (
    <>
      <SectionCard title="API Clients">
        <Stack spacing={2}>
          {/* Description and CTA share one row. `alignItems: flex-start`
          pins the button to the top so the description wraps cleanly
          underneath it instead of being vertically centred against
          the button (which made the layout feel lopsided). */}
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
            <Typography
              variant="body2"
              color="text.secondary"
              sx={{ flexGrow: 1 }}
            >
              API Clients let an external integration trade an OIDC access token
              from your IdP for a Rhesis access token (RFC 8693). Configure the
              IdP under <strong>Single Sign-On</strong> first; clients only work
              for organizations with SSO enabled and a slug set.
            </Typography>
            <Button
              variant="contained"
              color="primary"
              startIcon={<AddIcon />}
              onClick={openCreateDrawer}
              sx={{ flexShrink: 0 }}
            >
              Create
            </Button>
          </Box>

          {loadError && <Alert severity="error">{loadError}</Alert>}

          <ApiClientsList
            clients={clients}
            loading={loading}
            onRotate={handleRotate}
            onDisable={handleDisable}
            onEnable={handleEnable}
            onDelete={handleDelete}
          />
        </Stack>
      </SectionCard>
      {drawers}
    </>
  );
}

/**
 * Drop the plaintext `client_secret` field before pushing a row
 * into the list state. Defence in depth: even though the list view
 * never reads `client_secret`, removing it from the in-memory shape
 * means a future bug that JSON-serialises `clients` (e.g. for
 * debugging) cannot accidentally include the value.
 */
function stripSecret(row: AuthClientCreated): AuthClient {
  // Destructure to discard `client_secret`; the underscore tells
  // ESLint we know the variable is intentionally unused.
  const { client_secret: _ignored, ...rest } = row;
  void _ignored;
  return rest;
}
