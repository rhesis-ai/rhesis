'use client';

import * as React from 'react';
import Box from '@mui/material/Box';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AuditApiAccessCard, { AuditReadAccessCard } from './AuditApiAccessCard';
import AuditExportsSection from './AuditExportsSection';
import {
  AuditPrivacyCard,
  AuditRetentionCard,
  AuditSettingsNotices,
} from './AuditSettingsCards';
import StreamingSection from './StreamingSection';

// Two columns from the lg breakpoint; each card keeps its own height.
const gridSx = {
  display: 'grid',
  gridTemplateColumns: { xs: '1fr', lg: 'repeat(2, minmax(0, 1fr))' },
  columnGap: 3,
  alignItems: 'start',
} as const;

/** "Retention, export & access": each card shows only for those who can use it. */
export default function AuditSettingsTab() {
  const canRead = useCan(Capability.AuditLog.READ);
  const canExport = useCan(Capability.AuditLog.EXPORT);
  const canManage = useCan(Capability.AuditLog.MANAGE);

  return (
    <Box>
      {canRead && <AuditSettingsNotices />}
      {/* SectionCard brings its own bottom margin, so rows need no gap. */}
      <Box sx={gridSx}>
        {canRead && <AuditRetentionCard />}
        {canManage && <StreamingSection />}
        {canRead && <AuditReadAccessCard />}
        {canRead && <AuditPrivacyCard />}
        {canExport && <AuditExportsSection />}
        {canRead && <AuditApiAccessCard />}
      </Box>
    </Box>
  );
}
