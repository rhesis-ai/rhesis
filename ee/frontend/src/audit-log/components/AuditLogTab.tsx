'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import AccessDenied from '@/components/common/AccessDenied';
import { useCanWithStatus } from '@/components/common/Can';
import DetailTabNav from '@/components/common/DetailTabNav';
import { Capability } from '@/constants/capabilities';
import AuditEventsGrid from './AuditEventsGrid';

/**
 * The audit log's own sections. Settings, export, API access and streaming
 * join this list as their PRs land, each with the capability that guards it.
 */
const SECTIONS = [
  {
    id: 'events',
    label: 'Events',
    capability: Capability.AuditLog.READ,
    component: AuditEventsGrid,
  },
] as const;

export default function AuditLogTab() {
  const [active, setActive] = React.useState(0);
  const section = SECTIONS[active] ?? SECTIONS[0];
  const { allowed, loading } = useCanWithStatus(section.capability);
  const Section = section.component;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Typography variant="h6">Audit Log</Typography>
        <Typography variant="body2" color="text.secondary">
          Every change to access, test assets and configuration across your
          organization. Entries are append-only and cannot be edited or deleted.
        </Typography>
      </Box>

      {SECTIONS.length > 1 && (
        <DetailTabNav
          tabs={SECTIONS.map((s, index) => ({
            key: s.id,
            label: s.label,
            id: `audit-log-tab-${index}`,
            'aria-controls': `audit-log-tabpanel-${index}`,
          }))}
          activeIndex={active}
          onChange={setActive}
          aria-label="Audit log sections"
        />
      )}

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
          <CircularProgress />
        </Box>
      ) : allowed ? (
        <Section />
      ) : (
        <AccessDenied resource="the audit log" />
      )}
    </Box>
  );
}
