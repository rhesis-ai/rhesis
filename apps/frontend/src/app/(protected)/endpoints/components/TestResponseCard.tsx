'use client';

import React, { useState } from 'react';
import {
  Box,
  Button,
  ButtonGroup,
  Chip,
  CircularProgress,
  Collapse,
  Menu,
  MenuItem,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  CheckCircleIcon,
  KeyboardArrowDownIcon,
  KeyboardArrowUpIcon,
} from '@/components/icons';
import { BORDER_RADIUS } from '@/styles/theme';
import { JsonPreview } from './JsonPreview';
import {
  CardSubtitle,
  MappingCard,
  TestStatusBox,
  disabledContainedSx,
} from './MappingRows';
import { testPreviewSx } from './endpoint-styles';
import { mappingTarget } from './responsePaths';

export interface EndpointTestResult {
  success: boolean;
  status?: number;
  response?: Record<string, unknown>;
  error?: string;
}

export function RunTestButton({
  label,
  onRun,
  isTesting,
  blockedReason,
  variant = 'contained',
  menuItems,
}: {
  label: string;
  onRun: () => void;
  isTesting: boolean;
  /** Why the test can't run yet; the button is disabled while set. */
  blockedReason?: string;
  variant?: 'contained' | 'outlined';
  /** Extra actions behind an arrow beside the button, e.g. editing the test request. */
  menuItems?: { label: string; onClick: () => void }[];
}) {
  const [menuAnchor, setMenuAnchor] = useState<HTMLElement | null>(null);
  const disabled = Boolean(blockedReason);
  const runButton = (
    <Button
      variant={variant}
      onClick={onRun}
      disabled={disabled}
      loading={isTesting}
      sx={disabledContainedSx}
    >
      {label}
    </Button>
  );

  return (
    <Tooltip title={blockedReason ?? ''}>
      <Box component="span" sx={{ alignSelf: 'flex-start' }}>
        {menuItems?.length ? (
          <>
            <ButtonGroup variant={variant} disabled={disabled}>
              {runButton}
              <Button
                size="small"
                aria-label="More test request options"
                aria-haspopup="menu"
                onClick={e => setMenuAnchor(e.currentTarget)}
                sx={disabledContainedSx}
              >
                <KeyboardArrowDownIcon fontSize="small" />
              </Button>
            </ButtonGroup>
            <Menu
              anchorEl={menuAnchor}
              open={Boolean(menuAnchor)}
              onClose={() => setMenuAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
              {menuItems.map(item => (
                <MenuItem
                  key={item.label}
                  onClick={() => {
                    setMenuAnchor(null);
                    item.onClick();
                  }}
                >
                  {item.label}
                </MenuItem>
              ))}
            </Menu>
          </>
        ) : (
          runButton
        )}
      </Box>
    </Tooltip>
  );
}

interface TestResponseCardProps {
  result: EndpointTestResult | null;
  isTesting: boolean;
  subtitle: string;
  /** Shown before any run, e.g. what to do to get a response. */
  emptyText: string;
  successTitle: string;
  /** Header action, e.g. a Run again button. */
  action?: React.ReactNode;
  /** Rendered under the success box. */
  children?: React.ReactNode;
  complete?: boolean;
}

/** The Response side of the Mapping and Test steps; same header in every state. */
export function TestResponseCard({
  result,
  isTesting,
  subtitle,
  emptyText,
  successTitle,
  action,
  children,
  complete,
}: TestResponseCardProps) {
  const failedTitle = result?.status
    ? `HTTP ${result.status} error from endpoint`
    : 'Test request failed';

  return (
    <MappingCard
      title="Response"
      subtitle={<CardSubtitle>{subtitle}</CardSubtitle>}
      complete={complete}
      // Success is a small chip beside the title, so the mapping rows don't shift down.
      action={
        result?.success ? (
          <Chip
            icon={<CheckCircleIcon />}
            label={successTitle}
            color="success"
            variant="outlined"
            size="small"
          />
        ) : (
          action
        )
      }
    >
      {!result ? (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            color: 'text.secondary',
          }}
        >
          {isTesting && <CircularProgress size={16} />}
          <Typography variant="body2">
            {isTesting ? 'Waiting for your API…' : emptyText}
          </Typography>
        </Box>
      ) : (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {!result.success && (
            <TestStatusBox
              status="error"
              title={failedTitle}
              detail={result.error}
            />
          )}
          {result.success && children}
          {!result.success && result.response && (
            <RawResponseCollapse
              label="Complete response returned by your API"
              value={mappingTarget(result.response)}
            />
          )}
        </Box>
      )}
    </MappingCard>
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
