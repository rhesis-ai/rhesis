'use client';

import * as React from 'react';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Button,
  Collapse,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { GREYSCALE, BORDER_RADIUS, BACKDROP_COLORS } from '@/styles/theme';

export type MetricFilter = 'all' | 'has_metrics' | 'no_metrics';

export interface BehaviorFilters {
  metricCount: MetricFilter;
}

export const EMPTY_BEHAVIOR_FILTERS: BehaviorFilters = {
  metricCount: 'all',
};

interface FilterSectionProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function FilterSection({
  title,
  children,
  defaultOpen = true,
}: FilterSectionProps) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <Box
      sx={{
        borderTop: `1px solid ${GREYSCALE.light.border}`,
        pt: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '20px',
      }}
    >
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          userSelect: 'none',
        }}
        onClick={() => setOpen(o => !o)}
      >
        <Typography
          sx={{
            fontSize: 18,
            fontWeight: 700,
            color: GREYSCALE.light.title,
            lineHeight: '25px',
          }}
        >
          {title}
        </Typography>
        {open ? (
          <KeyboardArrowUpIcon
            sx={{ fontSize: 20, color: GREYSCALE.light.label }}
          />
        ) : (
          <KeyboardArrowDownIcon
            sx={{ fontSize: 20, color: GREYSCALE.light.label }}
          />
        )}
      </Box>
      <Collapse in={open}>
        <Box sx={{ pb: '4px' }}>{children}</Box>
      </Collapse>
    </Box>
  );
}

const METRIC_OPTIONS: { value: MetricFilter; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'has_metrics', label: 'Has Metrics' },
  { value: 'no_metrics', label: 'No Metrics' },
];

interface BehaviorFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: BehaviorFilters;
  onApply: (filters: BehaviorFilters) => void;
}

export default function BehaviorFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: BehaviorFilterDrawerProps) {
  const [draft, setDraft] = React.useState<BehaviorFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const chipSx = (selected: boolean) => ({
    display: 'inline-flex',
    alignItems: 'center',
    px: '12px',
    py: '4px',
    borderRadius: BORDER_RADIUS.pill,
    fontSize: 13,
    fontWeight: selected ? 700 : 400,
    lineHeight: '20px',
    cursor: 'pointer',
    border: '1px solid',
    borderColor: selected ? 'primary.main' : GREYSCALE.light.border,
    bgcolor: selected ? 'primary.main' : 'transparent',
    color: selected ? '#fff' : GREYSCALE.light.body,
    transition: 'all 0.15s',
    whiteSpace: 'nowrap' as const,
    '&:hover': {
      borderColor: 'primary.main',
      bgcolor: selected ? 'primary.dark' : 'rgba(0,128,175,0.06)',
    },
  });

  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      variant="temporary"
      ModalProps={{ keepMounted: true }}
      PaperProps={{
        sx: {
          width: 430,
          display: 'flex',
          flexDirection: 'column',
          p: '30px',
          gap: '30px',
          boxSizing: 'border-box',
        },
      }}
      sx={{
        '& .MuiBackdrop-root': {
          backgroundColor: BACKDROP_COLORS.filter,
        },
      }}
    >
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <Typography
          sx={{
            fontSize: 22,
            fontWeight: 700,
            color: GREYSCALE.light.title,
            lineHeight: 1.1,
          }}
        >
          Filter
        </Typography>
        <IconButton
          onClick={onClose}
          size="small"
          aria-label="Close filter"
          sx={{ color: GREYSCALE.light.label }}
        >
          <CloseIcon fontSize="small" />
        </IconButton>
      </Box>

      {/* Filter sections */}
      <Box
        sx={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: '30px',
          pt: '4px',
        }}
      >
        <FilterSection title="Metrics">
          <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {METRIC_OPTIONS.map(({ value, label }) => (
              <Box
                key={value}
                component="button"
                onClick={() =>
                  setDraft(prev => ({ ...prev, metricCount: value }))
                }
                sx={chipSx(draft.metricCount === value)}
              >
                {label}
              </Box>
            ))}
          </Box>
        </FilterSection>
      </Box>

      {/* Bottom toolbar */}
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'flex-end',
          gap: '10px',
          flexShrink: 0,
        }}
      >
        <Button
          variant="outlined"
          onClick={() => setDraft(EMPTY_BEHAVIOR_FILTERS)}
          sx={{
            borderWidth: 2,
            borderColor: 'primary.main',
            color: 'primary.main',
            fontWeight: 700,
            fontSize: 14,
            borderRadius: BORDER_RADIUS.sm,
            px: '16px',
            py: '8px',
            '&:hover': { borderWidth: 2 },
          }}
        >
          Reset
        </Button>
        <Button
          variant="contained"
          onClick={() => {
            onApply(draft);
            onClose();
          }}
          sx={{
            fontWeight: 700,
            fontSize: 14,
            borderRadius: BORDER_RADIUS.sm,
            px: '16px',
            py: '8px',
          }}
        >
          Apply
        </Button>
      </Box>
    </Drawer>
  );
}
