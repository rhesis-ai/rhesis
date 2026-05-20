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

export interface TestRunFilters {
  /** test_configuration/test_set/name contains */
  testSet: string;
  /** user/name contains (executor) */
  executor: string;
  /** tags contains */
  tag: string;
}

export const EMPTY_TEST_RUN_FILTERS: TestRunFilters = {
  testSet: '',
  executor: '',
  tag: '',
};

export function hasActiveTestRunFilters(f: TestRunFilters): boolean {
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

// ── Main component ─────────────────────────────────────────────────────────────

interface TestRunFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestRunFilters;
  onApply: (filters: TestRunFilters) => void;
}

export default function TestRunFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: TestRunFilterDrawerProps) {
  const [draft, setDraft] = React.useState<TestRunFilters>(filters);

  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const handleReset = () => setDraft(EMPTY_TEST_RUN_FILTERS);

  const handleApply = () => {
    onApply(draft);
    onClose();
  };

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
        {/* Test Set */}
        <FilterSection title="Test Set">
          <TextField
            fullWidth
            placeholder="Filter by test set name…"
            value={draft.testSet}
            onChange={e =>
              setDraft(prev => ({ ...prev, testSet: e.target.value }))
            }
            sx={textFieldSx}
          />
        </FilterSection>

        {/* Executor */}
        <FilterSection title="Executor">
          <TextField
            fullWidth
            placeholder="Filter by executor name…"
            value={draft.executor}
            onChange={e =>
              setDraft(prev => ({ ...prev, executor: e.target.value }))
            }
            sx={textFieldSx}
          />
        </FilterSection>

        {/* Tags */}
        <FilterSection title="Tags">
          <TextField
            fullWidth
            placeholder="Filter by tag name…"
            value={draft.tag}
            onChange={e => setDraft(prev => ({ ...prev, tag: e.target.value }))}
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
