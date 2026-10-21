'use client';

import React, { useState } from 'react';
import { Box, Button, Collapse, Tooltip, Typography } from '@mui/material';
import { KeyboardArrowDownIcon, KeyboardArrowUpIcon } from '@/components/icons';
import { SectionCard } from '@/components/common/SectionCard';
import { BORDER_RADIUS } from '@/styles/theme';
import { JsonPreview } from './JsonPreview';
import {
  CardSubtitle,
  TestStatusBox,
  disabledContainedSx,
} from './MappingRows';
import { testPreviewSx } from './endpoint-styles';

export interface EndpointTestResult {
  success: boolean;
  status?: number;
  response?: Record<string, unknown>;
  error?: string;
}

interface TestResponseCardProps {
  result: EndpointTestResult | null;
  isTesting: boolean;
  onRun: () => void;
  /** Why the test can't run yet; the button is disabled while set. */
  blockedReason?: string;
  emptyText: string;
  successTitle: string;
  /** Rendered under the success box. */
  children?: React.ReactNode;
}

export function TestResponseCard({
  result,
  isTesting,
  onRun,
  blockedReason,
  emptyText,
  successTitle,
  children,
}: TestResponseCardProps) {
  const runButton = (label: string, variant: 'contained' | 'outlined') => (
    <Tooltip title={blockedReason ?? ''}>
      <span>
        <Button
          variant={variant}
          onClick={onRun}
          disabled={Boolean(blockedReason)}
          loading={isTesting}
          sx={disabledContainedSx}
        >
          {label}
        </Button>
      </span>
    </Tooltip>
  );

  if (!result) {
    return (
      <SectionCard>
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: 2,
          }}
        >
          <Typography variant="h6" sx={{ fontWeight: 600 }} color="primary">
            No response yet
          </Typography>
          <Typography variant="body2">{emptyText}</Typography>
          {runButton('Run test request', 'contained')}
        </Box>
      </SectionCard>
    );
  }

  const failedTitle = result.status
    ? `HTTP ${result.status} error from endpoint`
    : 'Test request failed';

  return (
    <SectionCard
      title="Response"
      subtitle={
        <CardSubtitle>
          Run a test to see your API&apos;s response and map its fields.
        </CardSubtitle>
      }
      actions={runButton('Run again', 'outlined')}
    >
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {result.success ? (
          <TestStatusBox status="success" title={successTitle} />
        ) : (
          <TestStatusBox
            status="error"
            title={failedTitle}
            detail={result.error}
          />
        )}
        {result.success && children}
      </Box>
    </SectionCard>
  );
}

/** Collapsible view of the whole response, for when the mapped fields aren't enough. */
export function RawResponseCollapse({
  label,
  value,
}: {
  label: string;
  value: unknown;
}) {
  const [open, setOpen] = useState(false);
  return (
    <Box
      sx={{
        border: 1,
        borderColor: 'greyscale.border',
        borderRadius: BORDER_RADIUS.xs,
      }}
    >
      <Button
        fullWidth
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        endIcon={open ? <KeyboardArrowUpIcon /> : <KeyboardArrowDownIcon />}
        sx={{ justifyContent: 'flex-start', px: 1.25, py: 1 }}
      >
        {label}
      </Button>
      <Collapse in={open}>
        <Box sx={{ px: 1.25, pb: 1.25 }}>
          <Box component="pre" sx={{ ...testPreviewSx, maxHeight: 400 }}>
            {typeof value === 'string' ? value : <JsonPreview value={value} />}
          </Box>
        </Box>
      </Collapse>
    </Box>
  );
}
