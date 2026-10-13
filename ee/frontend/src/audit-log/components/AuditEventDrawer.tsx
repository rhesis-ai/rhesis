'use client';

import * as React from 'react';
import Link from 'next/link';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Collapse from '@mui/material/Collapse';
import List from '@mui/material/List';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemText from '@mui/material/ListItemText';
import Typography from '@mui/material/Typography';
import type { Theme } from '@mui/material/styles';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import { useQuery } from '@tanstack/react-query';
import BaseDrawer from '@/components/common/BaseDrawer';
import { useNotifications } from '@/components/common/NotificationContext';
import { BORDER_RADIUS } from '@/styles/theme-constants';
import { escapeODataValue } from '@/utils/odata-filter';
import { resourceDisplayName } from '../../shared/resource-catalog';
import {
  AUDIT_EVENTS_MAX_LIMIT,
  AuditLogClient,
} from '../api/audit-log-client';
import { auditLogQueryKeys } from '../filters';
import {
  actionLabel,
  actorDisplay,
  actorTypeLabel,
  channelLabel,
  jobUrl,
  outcomeLabel,
  resourceUrl,
  splitAction,
} from '../labels';
import { AuditOutcome, type AuditEvent, type AuditEventDetail } from '../types';
import AuditChanges, { monoSx } from './AuditChanges';

const AUDIT_DRAWER_WIDTH = 720;

function formatTime(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? iso : date.toLocaleString();
}

function Section({
  title,
  aside,
  children,
}: {
  title: string;
  aside?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
      <Box
        sx={{
          display: 'flex',
          alignItems: 'baseline',
          justifyContent: 'space-between',
          gap: 2,
        }}
      >
        <Typography variant="subtitle1" fontWeight="bold">
          {title}
        </Typography>
        {aside && (
          <Typography variant="caption" color="text.secondary">
            {aside}
          </Typography>
        )}
      </Box>
      {children}
    </Box>
  );
}

function Fact({
  label,
  children,
  mono = false,
}: {
  label: string;
  children: React.ReactNode;
  mono?: boolean;
}) {
  return (
    <>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography
        variant="body2"
        component="div"
        sx={mono ? monoSx : { minWidth: 0, overflowWrap: 'anywhere' }}
      >
        {children}
      </Typography>
    </>
  );
}

const factsSx = {
  display: 'grid',
  gridTemplateColumns: (t: Theme) => `${t.spacing(16)} 1fr`,
  columnGap: 2,
  rowGap: 1,
};

function Facts({ event }: { event: AuditEventDetail }) {
  const actor = actorDisplay(event);
  return (
    <Box sx={factsSx}>
      <Fact label="Actor">
        {actor.name}
        {actor.detail && (
          <Typography variant="caption" color="text.secondary" component="div">
            {actor.detail}
          </Typography>
        )}
      </Fact>
      <Fact label="Actor type">{actorTypeLabel(event.actor_type)}</Fact>
      <Fact label="Source">
        {channelLabel(event.channel)}
        {event.user_agent && (
          <Typography variant="caption" color="text.secondary" component="div">
            {event.user_agent}
          </Typography>
        )}
      </Fact>
      {event.ip && (
        <Fact label="IP address" mono>
          {event.ip}
        </Fact>
      )}
      <Fact label="Result">
        <Box
          component="span"
          sx={{
            color:
              event.outcome === AuditOutcome.SUCCESS
                ? 'success.main'
                : 'error.main',
            fontWeight: 'bold',
          }}
        >
          {outcomeLabel(event.outcome)}
        </Box>
        {event.status_code !== null && ` (HTTP ${event.status_code})`}
      </Fact>
      <Fact label="Occurred">{formatTime(event.occurred_at)}</Fact>
      <Fact label="Event ID" mono>
        {event.id}
      </Fact>
      {event.request_id && (
        <Fact label="Request ID" mono>
          {event.request_id}
        </Fact>
      )}
      <Fact label="Trace ID" mono>
        {event.trace_id}
      </Fact>
      {event.job_id && (
        <Fact label="Job" mono>
          {event.job_id}
        </Fact>
      )}
    </Box>
  );
}

function RelatedEvents({
  event,
  onSelect,
}: {
  event: AuditEvent;
  onSelect: (id: string) => void;
}) {
  // Loaded on request: most opens never need them, and each list read is audited.
  const [shown, setShown] = React.useState(false);
  const { data, isLoading, error } = useQuery({
    queryKey: auditLogQueryKeys.related(event.trace_id),
    queryFn: () =>
      new AuditLogClient().listEvents({
        $filter: `trace_id eq '${escapeODataValue(event.trace_id)}'`,
        limit: AUDIT_EVENTS_MAX_LIMIT,
        sort_order: 'asc',
      }),
    enabled: shown,
  });
  const others = (data?.data ?? []).filter(e => e.id !== event.id);
  const truncated = (data?.pagination.totalCount ?? 0) > AUDIT_EVENTS_MAX_LIMIT;

  if (!shown) {
    return (
      <Box>
        <Button size="small" onClick={() => setShown(true)}>
          Show events from the same request or job
        </Button>
      </Box>
    );
  }

  if (isLoading) return <CircularProgress size={20} />;
  if (error) {
    return (
      <Typography variant="body2" color="error">
        Could not load related events.
      </Typography>
    );
  }
  if (others.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No other events from the same request or job.
      </Typography>
    );
  }
  return (
    <>
      <List
        dense
        disablePadding
        sx={{
          border: (t: Theme) => `1px solid ${t.palette.greyscale.border}`,
          borderRadius: BORDER_RADIUS.sm,
        }}
      >
        {others.map(other => (
          <ListItemButton key={other.id} onClick={() => onSelect(other.id)}>
            <ListItemText
              primary={actionLabel(other.action, other.outcome)}
              secondary={[other.resource_label, formatTime(other.occurred_at)]
                .filter(Boolean)
                .join(' · ')}
            />
          </ListItemButton>
        ))}
      </List>
      {truncated && (
        <Typography variant="caption" color="text.secondary">
          Showing the first {AUDIT_EVENTS_MAX_LIMIT}. Filter the log by trace ID{' '}
          {event.trace_id} to see them all.
        </Typography>
      )}
    </>
  );
}

function EventBody({
  event,
  onSelect,
}: {
  event: AuditEventDetail;
  onSelect: (id: string) => void;
}) {
  const notifications = useNotifications();
  const [showJson, setShowJson] = React.useState(false);
  const json = React.useMemo(() => JSON.stringify(event, null, 2), [event]);
  const url = resourceUrl(event);
  const { resource } = splitAction(event.action);

  const copyJson = React.useCallback(async () => {
    try {
      await navigator.clipboard.writeText(json);
      notifications.show('Event JSON copied', { severity: 'success' });
    } catch {
      notifications.show('Could not copy to the clipboard', {
        severity: 'error',
      });
    }
  }, [json, notifications]);

  return (
    <>
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
        <Typography variant="body2" sx={monoSx} color="text.secondary">
          {event.action}
        </Typography>
        <Typography variant="h6">
          {resourceDisplayName(resource)}
          {event.resource_label && ` · ${event.resource_label}`}
        </Typography>
      </Box>

      <Facts event={event} />

      <Section title="Changes" aside="Secrets are never recorded">
        <AuditChanges event={event} />
      </Section>

      <Section title="Related events">
        <RelatedEvents event={event} onSelect={onSelect} />
      </Section>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
        {url && (
          <Button
            component={Link}
            href={url}
            variant="outlined"
            size="small"
            startIcon={<OpenInNewIcon />}
          >
            Open {resourceDisplayName(resource)}
          </Button>
        )}
        {event.job_id && (
          <Button
            component={Link}
            href={jobUrl(event.job_id)}
            variant="outlined"
            size="small"
            startIcon={<OpenInNewIcon />}
          >
            Open job
          </Button>
        )}
        <Button
          variant="outlined"
          size="small"
          startIcon={<ContentCopyIcon />}
          onClick={copyJson}
        >
          Copy JSON
        </Button>
        <Button size="small" onClick={() => setShowJson(v => !v)}>
          {showJson ? 'Hide raw event' : 'Show raw event'}
        </Button>
      </Box>

      <Collapse in={showJson} unmountOnExit>
        <Box
          component="pre"
          sx={{
            ...monoSx,
            m: 0,
            p: 2,
            whiteSpace: 'pre-wrap',
            bgcolor: 'action.hover',
            borderRadius: BORDER_RADIUS.sm,
            typography: 'caption',
          }}
        >
          {json}
        </Box>
      </Collapse>
    </>
  );
}

interface AuditEventDrawerProps {
  /** The event to show; null closes the drawer. */
  eventId: string | null;
  onClose: () => void;
  /** Open another event in the same drawer (related events). */
  onSelect: (id: string) => void;
}

export default function AuditEventDrawer({
  eventId,
  onClose,
  onSelect,
}: AuditEventDrawerProps) {
  // Keep showing the last event while the drawer slides out, without fetching
  // once closed (each read is audited).
  const [shownId, setShownId] = React.useState(eventId);
  React.useEffect(() => {
    if (eventId) setShownId(eventId);
  }, [eventId]);
  const { data, isLoading, error } = useQuery({
    queryKey: auditLogQueryKeys.event(shownId ?? ''),
    queryFn: () => new AuditLogClient().getEvent(shownId ?? ''),
    enabled: !!eventId && eventId === shownId,
  });

  const title = data ? actionLabel(data.action, data.outcome) : 'Event';

  return (
    <BaseDrawer
      open={!!eventId}
      onClose={onClose}
      title={title}
      closeButtonText="Close"
      width={AUDIT_DRAWER_WIDTH}
    >
      {isLoading && (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      )}
      {error && (
        <Alert severity="error">
          {error instanceof Error ? error.message : 'Could not load the event.'}
        </Alert>
      )}
      {data && <EventBody event={data} onSelect={onSelect} />}
    </BaseDrawer>
  );
}
