'use client';

import * as React from 'react';
import { Box, IconButton, Stack } from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { SectionCard } from '@/components/common/SectionCard';
import ViewField from '@/components/common/ViewField';

/**
 * A collapsible report card for the details at the end of a report. Closed on
 * screen until its header is clicked, always open when printed, so the PDF
 * carries everything.
 */
export default function ReportFold({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: React.ReactNode;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <SectionCard
      title={title}
      subtitle={subtitle}
      onHeaderClick={() => setOpen(prev => !prev)}
      actions={
        <IconButton
          size="small"
          aria-label={open ? `Collapse ${title}` : `Expand ${title}`}
          aria-expanded={open}
          sx={{ displayPrint: 'none' }}
        >
          <ExpandMoreIcon
            sx={{ transform: open ? 'rotate(180deg)' : 'none' }}
          />
        </IconButton>
      }
    >
      <Box sx={{ display: open ? 'block' : 'none', displayPrint: 'block' }}>
        <Stack spacing={3}>{children}</Stack>
      </Box>
    </SectionCard>
  );
}

/** One read-only field inside a fold. */
export function ReportFoldRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return typeof children === 'string' || typeof children === 'number' ? (
    <ViewField label={label} value={children} />
  ) : (
    <ViewField label={label}>{children}</ViewField>
  );
}
