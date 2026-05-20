'use client';

import * as React from 'react';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Button,
  Collapse,
  TextField,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { GREYSCALE, BORDER_RADIUS, BACKDROP_COLORS } from '@/styles/theme';

// ── Filter state ───────────────────────────────────────────────────────────────

export interface MetricDrawerFilters {
  type: string[];
  scoreType: string[];
  metricScope: string[];
  behavior: string;
}

export const EMPTY_METRIC_DRAWER_FILTERS: MetricDrawerFilters = {
  type: [],
  scoreType: [],
  metricScope: [],
  behavior: '',
};

export function hasActiveMetricDrawerFilters(f: MetricDrawerFilters): boolean {
  return (
    f.type.length > 0 ||
    f.scoreType.length > 0 ||
    f.metricScope.length > 0 ||
    f.behavior !== ''
  );
}

// ── Sub-components ─────────────────────────────────────────────────────────────

interface SectionProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
}

function FilterSection({ title, children, defaultOpen = true }: SectionProps) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <Box
      sx={{
        borderTop: `1px solid ${GREYSCALE.light.border}`,
        pt: '20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
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

// ── Filter options ─────────────────────────────────────────────────────────────

const METRIC_TYPE_LABELS: Record<string, string> = {
  'custom-prompt': 'LLM Judge',
  'api-call': 'External API',
  'custom-code': 'Script',
  grading: 'Grades',
  framework: 'Framework',
};

// ── Main component ─────────────────────────────────────────────────────────────

export interface MetricFilterOptions {
  type: { type_value: string; description: string }[];
  scoreType: { value: string; label: string }[];
  metricScope: { value: string; label: string }[];
}

interface MetricFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: MetricDrawerFilters;
  filterOptions: MetricFilterOptions;
  onApply: (filters: MetricDrawerFilters) => void;
}

export default function MetricFilterDrawer({
  open,
  onClose,
  filters,
  filterOptions,
  onApply,
}: MetricFilterDrawerProps) {
  const [draft, setDraft] = React.useState<MetricDrawerFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_METRIC_DRAWER_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

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

  const textFieldSx = {
    '& .MuiOutlinedInput-root': {
      borderRadius: BORDER_RADIUS.sm,
      fontSize: 14,
    },
    '& .MuiOutlinedInput-input': {
      padding: '20px 14px',
    },
  };

  const toggleMulti = (
    key: keyof Pick<MetricDrawerFilters, 'type' | 'scoreType' | 'metricScope'>,
    value: string
  ) => {
    setDraft(prev => {
      const arr = prev[key];
      return {
        ...prev,
        [key]: arr.includes(value)
          ? arr.filter(v => v !== value)
          : [...arr, value],
      };
    });
  };

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
        {/* Metric Type */}
        {filterOptions.type.length > 0 && (
          <FilterSection title="Type">
            <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {filterOptions.type.map(opt => (
                <Box
                  key={opt.type_value}
                  component="button"
                  onClick={() => toggleMulti('type', opt.type_value)}
                  sx={chipSx(draft.type.includes(opt.type_value))}
                >
                  {METRIC_TYPE_LABELS[opt.type_value] ?? opt.type_value}
                </Box>
              ))}
            </Box>
          </FilterSection>
        )}

        {/* Score Type */}
        {filterOptions.scoreType.length > 0 && (
          <FilterSection title="Score Type">
            <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {filterOptions.scoreType.map(opt => (
                <Box
                  key={opt.value}
                  component="button"
                  onClick={() => toggleMulti('scoreType', opt.value)}
                  sx={chipSx(draft.scoreType.includes(opt.value))}
                >
                  {opt.label}
                </Box>
              ))}
            </Box>
          </FilterSection>
        )}

        {/* Metric Scope */}
        {filterOptions.metricScope.length > 0 && (
          <FilterSection title="Metric Scope">
            <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {filterOptions.metricScope.map(opt => (
                <Box
                  key={opt.value}
                  component="button"
                  onClick={() => toggleMulti('metricScope', opt.value)}
                  sx={chipSx(draft.metricScope.includes(opt.value))}
                >
                  {opt.label}
                </Box>
              ))}
            </Box>
          </FilterSection>
        )}

        {/* Behavior */}
        <FilterSection title="Behavior">
          <TextField
            fullWidth
            placeholder="Filter by behavior name…"
            value={draft.behavior}
            onChange={e =>
              setDraft(prev => ({ ...prev, behavior: e.target.value }))
            }
            sx={textFieldSx}
          />
        </FilterSection>
      </Box>

      {/* Footer buttons */}
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
          onClick={handleReset}
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
          onClick={handleApply}
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
