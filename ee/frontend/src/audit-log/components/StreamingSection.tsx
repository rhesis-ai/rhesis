'use client';

import * as React from 'react';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Link from '@mui/material/Link';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { Add as AddIcon } from '@mui/icons-material';
import StreamIcon from '@mui/icons-material/Stream';
import { SectionCard } from '@/components/common/SectionCard';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import { useNotifications } from '@/components/common/NotificationContext';
import { getApiErrorMessage } from '@/utils/error-utils';
import { AuditDestinationsClient } from '../api/audit-destinations-client';
import {
  STANDARD_WEBHOOKS_URL,
  withoutSecret,
  type AuditDestination,
  type AuditDestinationCreate,
  type AuditDestinationCreated,
} from '../destinations';
import CreateDestinationDrawer from './CreateDestinationDrawer';
import DestinationsList from './DestinationsList';
import SigningSecretDrawer from './SigningSecretDrawer';

const NOT_FOUND = 404;
const UNAVAILABLE =
  'Streaming is not available. Check that your Enterprise licence is active.';
const OK_TOAST = { severity: 'success', autoHideDuration: 3000 } as const;
const ERROR_TOAST = { severity: 'error', autoHideDuration: 8000 } as const;

const EMPTY_DESCRIPTION =
  'Send every audit event to a webhook, Splunk or Datadog. A destination ' +
  'receives the events recorded after you add it.';

function loadErrorMessage(err: unknown): string {
  const status = (err as { status?: number } | null)?.status;
  return status === NOT_FOUND
    ? UNAVAILABLE
    : getApiErrorMessage(err, 'Failed to load destinations');
}

function DeliveryNotes() {
  return (
    <Stack spacing={1}>
      <Typography variant="body2" color="text.secondary">
        Events arrive within seconds of being recorded. Delivery is at least
        once, so the same event can arrive twice. Drop duplicates by the
        event&apos;s <code>id</code>.
      </Typography>
      <Typography variant="body2" color="text.secondary">
        Webhooks are signed with{' '}
        <Link href={STANDARD_WEBHOOKS_URL} target="_blank" rel="noopener">
          Standard Webhooks
        </Link>
        . Verify the <code>webhook-signature</code> header with the signing
        secret. Content values are never streamed, and IP addresses follow your
        organization&apos;s masking setting.
      </Typography>
    </Stack>
  );
}

export default function StreamingSection() {
  const notifications = useNotifications();
  const client = React.useMemo(() => new AuditDestinationsClient(), []);

  const [destinations, setDestinations] = React.useState<AuditDestination[]>(
    []
  );
  const [loading, setLoading] = React.useState(true);
  const [loadError, setLoadError] = React.useState<string | null>(null);
  const [createOpen, setCreateOpen] = React.useState(false);
  const [createError, setCreateError] = React.useState<string | null>(null);
  // Holds the one-time secret until acknowledged; never stored elsewhere.
  const [revealing, setRevealing] =
    React.useState<AuditDestinationCreated | null>(null);
  const [testing, setTesting] = React.useState<ReadonlySet<string>>(new Set());

  const load = React.useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setDestinations(await client.listDestinations());
    } catch (err: unknown) {
      setLoadError(loadErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [client]);

  React.useEffect(() => {
    load();
  }, [load]);

  const replace = (row: AuditDestination) =>
    setDestinations(prev => prev.map(d => (d.id === row.id ? row : d)));

  const handleCreate = async (body: AuditDestinationCreate) => {
    setCreateError(null);
    try {
      const created = await client.createDestination(body);
      setCreateOpen(false);
      setDestinations(prev => [...prev, withoutSecret(created)]);
      if (created.signing_secret) {
        setRevealing(created);
      } else {
        notifications.show('Destination added', OK_TOAST);
      }
    } catch (err: unknown) {
      setCreateError(getApiErrorMessage(err, 'Failed to add destination'));
      throw err;
    }
  };

  const handleSetPaused = async (d: AuditDestination, paused: boolean) => {
    try {
      replace(await client.setPaused(d.id, paused));
      notifications.show(
        paused ? 'Destination paused' : 'Destination resumed',
        OK_TOAST
      );
    } catch (err: unknown) {
      notifications.show(
        getApiErrorMessage(
          err,
          paused ? 'Failed to pause destination' : 'Failed to resume'
        ),
        ERROR_TOAST
      );
    }
  };

  const handleDelete = async (d: AuditDestination) => {
    try {
      await client.deleteDestination(d.id);
      setDestinations(prev => prev.filter(x => x.id !== d.id));
      notifications.show('Destination deleted', OK_TOAST);
    } catch (err: unknown) {
      notifications.show(
        getApiErrorMessage(err, 'Failed to delete destination'),
        ERROR_TOAST
      );
    }
  };

  const handleTest = async (d: AuditDestination) => {
    setTesting(prev => new Set(prev).add(d.id));
    try {
      const result = await client.sendTestEvent(d.id);
      if (result.delivered) {
        notifications.show(`Test event delivered to ${d.name}`, OK_TOAST);
      } else {
        notifications.show(
          `Test event to ${d.name} failed: ${result.error ?? 'unknown error'}`,
          ERROR_TOAST
        );
      }
    } catch (err: unknown) {
      notifications.show(
        getApiErrorMessage(err, 'Failed to send test event'),
        ERROR_TOAST
      );
    } finally {
      setTesting(prev => {
        const next = new Set(prev);
        next.delete(d.id);
        return next;
      });
    }
  };

  const openCreate = () => {
    setCreateError(null);
    setCreateOpen(true);
  };

  const drawers = (
    <>
      <CreateDestinationDrawer
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onSubmit={handleCreate}
        errorMessage={createError}
      />
      {revealing?.signing_secret && (
        <SigningSecretDrawer
          open
          destinationName={revealing.name}
          secret={revealing.signing_secret}
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

  if (loadError) {
    return (
      <SectionCard>
        <Alert
          severity="error"
          action={
            <Button color="inherit" size="small" onClick={load}>
              Retry
            </Button>
          }
        >
          {loadError}
        </Alert>
      </SectionCard>
    );
  }

  if (destinations.length === 0) {
    return (
      <>
        <SectionCard>
          <SectionEmptyState
            icon={StreamIcon}
            title="No streaming destinations yet"
            description={EMPTY_DESCRIPTION}
            actionLabel="Add destination"
            onAction={openCreate}
            showAddIcon
            inset={false}
          />
          <DeliveryNotes />
        </SectionCard>
        {drawers}
      </>
    );
  }

  return (
    <>
      <SectionCard title="Streaming">
        <Stack spacing={2}>
          <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 2 }}>
            <Box sx={{ flexGrow: 1 }}>
              <DeliveryNotes />
            </Box>
            <Button
              variant="contained"
              startIcon={<AddIcon />}
              onClick={openCreate}
              sx={{ flexShrink: 0 }}
            >
              Add
            </Button>
          </Box>
          <DestinationsList
            destinations={destinations}
            testing={testing}
            onTest={handleTest}
            onSetPaused={handleSetPaused}
            onDelete={handleDelete}
          />
        </Stack>
      </SectionCard>
      {drawers}
    </>
  );
}
