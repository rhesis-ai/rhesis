'use client';

import Chip from '@mui/material/Chip';
import type { ReportStatus } from '@/utils/api-client/interfaces/report';

const LABELS: Record<ReportStatus, string> = {
  draft: 'Draft',
  published: 'Published',
};

export default function ReportStatusChip({
  status,
  live = false,
}: {
  status: ReportStatus;
  /** On the report page a draft says its numbers are live. */
  live?: boolean;
}) {
  return (
    <Chip
      size="small"
      variant="outlined"
      color={status === 'published' ? 'success' : 'warning'}
      label={status === 'draft' && live ? 'Draft · live data' : LABELS[status]}
    />
  );
}
