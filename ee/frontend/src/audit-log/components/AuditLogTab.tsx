'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import AccessDenied from '@/components/common/AccessDenied';
import { useCanWithStatus } from '@/components/common/Can';
import DetailTabNav from '@/components/common/DetailTabNav';
import { Capability } from '@/constants/capabilities';
import { useAuditLogSettings } from '../hooks/useAuditLogSettings';
import { retentionLabel } from '../retention';
import AuditEventsGrid from './AuditEventsGrid';
import AuditSettingsTab from './AuditSettingsTab';
import { StatusPill } from './tones';

/** The query parameter that selects a section; the export notification links to `settings`. */
export const AUDIT_LOG_SECTION_PARAM = 'section';

export const AuditLogSectionId = {
  EVENTS: 'events',
  SETTINGS: 'settings',
} as const;

/** Section ids from before retention, export, streaming and API access shared a tab. */
const LEGACY_SECTIONS: Record<string, string> = {
  exports: AuditLogSectionId.SETTINGS,
  streaming: AuditLogSectionId.SETTINGS,
  api: AuditLogSectionId.SETTINGS,
};

type CapabilityName =
  (typeof Capability.AuditLog)[keyof typeof Capability.AuditLog];

/** The audit log's own sections; any one of a section's capabilities opens it. */
const SECTIONS: readonly {
  id: string;
  label: string;
  description: string;
  capabilities: readonly CapabilityName[];
  component: React.ComponentType;
}[] = [
  {
    id: AuditLogSectionId.EVENTS,
    label: 'Events',
    description:
      'Every change to access, test assets and configuration across your organization. Entries are append-only and cannot be edited or deleted.',
    capabilities: [Capability.AuditLog.READ],
    component: AuditEventsGrid,
  },
  {
    id: AuditLogSectionId.SETTINGS,
    label: 'Retention, export & access',
    description:
      'Control how long events are kept, where they are streamed and who can read them.',
    capabilities: [
      Capability.AuditLog.READ,
      Capability.AuditLog.EXPORT,
      Capability.AuditLog.MANAGE,
    ],
    component: AuditSettingsTab,
  },
];

function RetentionBadge() {
  const { data } = useAuditLogSettings();
  if (!data) return null;
  return (
    <StatusPill tone="default">
      Retention: {retentionLabel(data.retention_days)}
    </StatusPill>
  );
}

export default function AuditLogTab() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const read = useCanWithStatus(Capability.AuditLog.READ);
  const exportStatus = useCanWithStatus(Capability.AuditLog.EXPORT);
  const manage = useCanWithStatus(Capability.AuditLog.MANAGE);
  const status: Record<string, { allowed: boolean; loading: boolean }> = {
    [Capability.AuditLog.READ]: read,
    [Capability.AuditLog.EXPORT]: exportStatus,
    [Capability.AuditLog.MANAGE]: manage,
  };
  const loading = read.loading || exportStatus.loading || manage.loading;
  // Only the sections the viewer can use get a tab.
  const visible = SECTIONS.filter(s =>
    s.capabilities.some(c => status[c]?.allowed)
  );
  const param = searchParams.get(AUDIT_LOG_SECTION_PARAM) ?? '';
  const requested = LEGACY_SECTIONS[param] ?? param;
  const section = visible.find(s => s.id === requested) ?? visible[0];
  const activeIndex = section ? visible.indexOf(section) : 0;

  const select = (index: number) => {
    const next = visible[index];
    if (!next) return;
    const params = new URLSearchParams(searchParams.toString());
    params.set(AUDIT_LOG_SECTION_PARAM, next.id);
    router.push(`?${params.toString()}`, { scroll: false });
  };

  let content: React.ReactNode;
  if (loading) {
    content = (
      <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
        <CircularProgress />
      </Box>
    );
  } else if (section) {
    const Section = section.component;
    content = <Section />;
  } else {
    content = <AccessDenied resource="the audit log" />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box
        sx={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 2,
        }}
      >
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
          <Typography variant="h4" component="h2">
            Audit Log
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {(section ?? SECTIONS[0]).description}
          </Typography>
        </Box>
        {read.allowed && <RetentionBadge />}
      </Box>

      {!loading && visible.length > 1 && (
        <DetailTabNav
          tabs={visible.map((s, index) => ({
            key: s.id,
            label: s.label,
            id: `audit-log-tab-${index}`,
            'aria-controls': `audit-log-tabpanel-${index}`,
          }))}
          activeIndex={activeIndex}
          onChange={select}
          aria-label="Audit log sections"
        />
      )}

      {content}
    </Box>
  );
}
