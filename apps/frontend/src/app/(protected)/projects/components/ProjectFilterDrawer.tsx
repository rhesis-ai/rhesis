'use client';

import * as React from 'react';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Switch,
  Button,
  Collapse,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { GREYSCALE, BORDER_RADIUS, BACKDROP_COLORS } from '@/styles/theme';

export interface ProjectFilters {
  activeStatus: boolean | null; // null = all, true = active only, false = inactive only
  environments: string[];
}

export const EMPTY_FILTERS: ProjectFilters = {
  activeStatus: null,
  environments: [],
};

export function hasActiveProjectFilters(f: ProjectFilters): boolean {
  return f.activeStatus !== null || f.environments.length > 0;
}

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

const ENVIRONMENTS = ['development', 'staging', 'production'] as const;
const ENV_LABELS: Record<string, string> = {
  development: 'Development',
  staging: 'Staging',
  production: 'Production',
};

interface ProjectFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: ProjectFilters;
  onApply: (filters: ProjectFilters) => void;
}

export default function ProjectFilterDrawer({
  open,
  onClose,
  filters,
  onApply,
}: ProjectFilterDrawerProps) {
  const [draft, setDraft] = React.useState<ProjectFilters>(filters);

  // Sync draft when drawer opens
  React.useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const toggleEnvironment = (env: string) => {
    setDraft(prev => ({
      ...prev,
      environments: prev.environments.includes(env)
        ? prev.environments.filter(e => e !== env)
        : [...prev.environments, env],
    }));
  };

  const handleReset = () => {
    setDraft(EMPTY_FILTERS);
  };

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

      {/* Filter sections — scrollable */}
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
        {/* Status section */}
        <FilterSection title="Status">
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
            {[
              { label: 'Active', value: true as const },
              { label: 'Inactive', value: false as const },
            ].map(({ label, value }) => (
              <Box
                key={label}
                sx={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  height: 38,
                }}
              >
                <Typography sx={{ fontSize: 14, color: GREYSCALE.light.body }}>
                  {label}
                </Typography>
                <Switch
                  checked={draft.activeStatus === value}
                  onChange={e => {
                    setDraft(prev => ({
                      ...prev,
                      activeStatus: e.target.checked ? value : null,
                    }));
                  }}
                  size="small"
                  sx={{
                    '& .MuiSwitch-switchBase.Mui-checked': {
                      color: 'primary.main',
                    },
                    '& .MuiSwitch-switchBase.Mui-checked + .MuiSwitch-track': {
                      bgcolor: 'primary.main',
                    },
                  }}
                />
              </Box>
            ))}
          </Box>
        </FilterSection>

        {/* Environment section */}
        <FilterSection title="Environment">
          <Box sx={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
            {ENVIRONMENTS.map(env => (
              <Box
                key={env}
                component="button"
                onClick={() => toggleEnvironment(env)}
                sx={chipSx(draft.environments.includes(env))}
              >
                {ENV_LABELS[env]}
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
