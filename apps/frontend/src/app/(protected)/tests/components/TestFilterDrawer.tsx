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

export interface TestFilters {
  /** test_type/type_value equals: 'single_turn' | 'multi_turn' | '' */
  testType: string;
  /** status/name contains */
  status: string;
  /** behavior/name contains */
  behavior: string;
  /** category/name contains */
  category: string;
  /** topic/name contains */
  topic: string;
}

export const EMPTY_TEST_FILTERS: TestFilters = {
  testType: '',
  status: '',
  behavior: '',
  category: '',
  topic: '',
};

export function hasActiveTestFilters(f: TestFilters): boolean {
  return Object.values(f).some(v => v !== '');
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

const TEST_TYPE_OPTIONS = [
  { label: 'Single Turn', value: 'single_turn' },
  { label: 'Multi Turn', value: 'multi_turn' },
] as const;

// ── Main component ─────────────────────────────────────────────────────────────

interface TestFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestFilters;
  onApply: (filters: TestFilters) => void;
}

export default function TestFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TestFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TestFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_TEST_FILTERS);

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
        {/* Test Type */}
        <FilterSection title="Test Type">
          <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {TEST_TYPE_OPTIONS.map(opt => (
              <Box
                key={opt.value}
                component="button"
                onClick={() =>
                  setDraft(prev => ({
                    ...prev,
                    testType: prev.testType === opt.value ? '' : opt.value,
                  }))
                }
                sx={chipSx(draft.testType === opt.value)}
              >
                {opt.label}
              </Box>
            ))}
          </Box>
        </FilterSection>

        {/* Status */}
        <FilterSection title="Status">
          <TextField
            fullWidth
            placeholder="e.g. Active, Draft…"
            value={draft.status}
            onChange={e =>
              setDraft(prev => ({ ...prev, status: e.target.value }))
            }
            sx={textFieldSx}
          />
        </FilterSection>

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

        {/* Category */}
        <FilterSection title="Category">
          <TextField
            fullWidth
            placeholder="Filter by category name…"
            value={draft.category}
            onChange={e =>
              setDraft(prev => ({ ...prev, category: e.target.value }))
            }
            sx={textFieldSx}
          />
        </FilterSection>

        {/* Topic */}
        <FilterSection title="Topic">
          <TextField
            fullWidth
            placeholder="Filter by topic name…"
            value={draft.topic}
            onChange={e =>
              setDraft(prev => ({ ...prev, topic: e.target.value }))
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
