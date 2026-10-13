'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Typography from '@mui/material/Typography';
import AccessDenied from '@/components/common/AccessDenied';
import { useCanWithStatus } from '@/components/common/Can';
import DetailTabNav from '@/components/common/DetailTabNav';
import { Capability } from '@/constants/capabilities';
import { useAuditLogSettings } from '../hooks/useAuditLogSettings';
import { retentionLabel } from '../retention';
import AuditApiAccessSection from './AuditApiAccessSection';
import AuditEventsGrid from './AuditEventsGrid';
import AuditExportsSection from './AuditExportsSection';
import AuditLogSettingsSection from './AuditLogSettingsSection';
import StreamingSection from './StreamingSection';

/** The query parameter that selects a section; the export notification links to `exports`. */
export const AUDIT_LOG_SECTION_PARAM = 'section';

export const AuditLogSectionId = {
  EVENTS: 'events',
  EXPORTS: 'exports',
  SETTINGS: 'settings',
  STREAMING: 'streaming',
  API: 'api',
} as const;

/** The audit log's own sections, each with the capability that guards it. */
const SECTIONS = [
  {
    id: AuditLogSectionId.EVENTS,
    label: 'Events',
    capability: Capability.AuditLog.READ,
    component: AuditEventsGrid,
  },
  {
    id: AuditLogSectionId.EXPORTS,
    label: 'Exports',
    capability: Capability.AuditLog.EXPORT,
    component: AuditExportsSection,
  },
  {
    id: AuditLogSectionId.SETTINGS,
    label: 'Settings',
    capability: Capability.AuditLog.READ,
    component: AuditLogSettingsSection,
  },
  {
    id: AuditLogSectionId.STREAMING,
    label: 'Streaming',
    capability: Capability.AuditLog.MANAGE,
    component: StreamingSection,
  },
  {
    id: AuditLogSectionId.API,
    label: 'API access',
    capability: Capability.AuditLog.READ,
    component: AuditApiAccessSection,
  },
] as const;

function RetentionBadge() {
  const { data } = useAuditLogSettings();
  if (!data) return null;
  return (
    <Chip
      size="small"
      variant="outlined"
      label={`Retention: ${retentionLabel(data.retention_days)}`}
    />
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
  const visible = SECTIONS.filter(s => status[s.capability]?.allowed);
  const requested = searchParams.get(AUDIT_LOG_SECTION_PARAM);
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
  } else if (section && status[section.capability]?.allowed) {
    const Section = section.component;
    content = <Section />;
  } else {
    content = <AccessDenied resource="the audit log" />;
  }

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <Box>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <Typography variant="h6">Audit Log</Typography>
          <RetentionBadge />
        </Box>
        <Typography variant="body2" color="text.secondary">
          Every change to access, test assets and configuration across your
          organization. Entries are append-only and cannot be edited or deleted.
        </Typography>
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
