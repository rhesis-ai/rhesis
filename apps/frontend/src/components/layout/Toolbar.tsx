'use client';

import React from 'react';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ButtonGroup from '@mui/material/ButtonGroup';
import IconButton from '@mui/material/IconButton';
import TextField from '@mui/material/TextField';
import InputAdornment from '@mui/material/InputAdornment';
import Tooltip from '@mui/material/Tooltip';
import Typography from '@mui/material/Typography';
import FilterListIcon from '@mui/icons-material/FilterList';
import SearchIcon from '@mui/icons-material/Search';
import ViewColumnIcon from '@mui/icons-material/ViewColumn';
import DensityMediumIcon from '@mui/icons-material/DensityMedium';
import FileDownloadIcon from '@mui/icons-material/FileDownload';
import { GREYSCALE, BORDER_RADIUS } from '@/styles/theme';

export interface PillTab {
  label: string;
  value: string;
}

export interface RightAction {
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  tooltip?: string;
}

export interface ToolbarProps {
  /** Search field props */
  searchProps?: {
    value: string;
    onChange: (v: string) => void;
    placeholder?: string;
  };
  /** Whether to show the filter icon button on the left */
  onFilterClick?: () => void;
  /** Pill tabs for tab-style filtering */
  pillTabs?: {
    tabs: PillTab[];
    activeValue: string;
    onChange: (v: string) => void;
  };
  /** Right-side action buttons (defaults: Columns, Density, Export) */
  rightActions?: RightAction[];
  /** Override entire right zone with arbitrary content */
  rightContent?: React.ReactNode;
}

const defaultRightActions: RightAction[] = [
  {
    label: 'Columns',
    icon: <ViewColumnIcon sx={{ fontSize: 18 }} />,
    onClick: () => {},
    tooltip: 'Manage columns',
  },
  {
    label: 'Density',
    icon: <DensityMediumIcon sx={{ fontSize: 18 }} />,
    onClick: () => {},
    tooltip: 'Change density',
  },
  {
    label: 'Export',
    icon: <FileDownloadIcon sx={{ fontSize: 18 }} />,
    onClick: () => {},
    tooltip: 'Export data',
  },
];

/**
 * Figma-aligned Toolbar component matching node 841:38328.
 *
 * Layout: [filter icon | search] ... [pill tabs] ... [Columns | Density | Export]
 */
export function Toolbar({
  searchProps,
  onFilterClick,
  pillTabs,
  rightActions,
  rightContent,
}: ToolbarProps) {
  const actions = rightActions ?? defaultRightActions;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1.5,
        width: '100%',
        minHeight: 48,
        px: 2,
        py: 1,
        borderBottom: theme =>
          `1px solid ${
            theme.palette.mode === 'light'
              ? GREYSCALE.light.border
              : GREYSCALE.dark.border
          }`,
      }}
    >
      {/* Left zone: filter button + search */}
      <Box
        sx={{ display: 'flex', alignItems: 'center', gap: 1, flexShrink: 0 }}
      >
        {onFilterClick && (
          <Tooltip title="Filters">
            <IconButton
              onClick={onFilterClick}
              size="small"
              sx={{
                bgcolor: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.surface1
                    : GREYSCALE.dark.surface1,
                borderRadius: BORDER_RADIUS.sm,
                border: theme =>
                  `1px solid ${
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.border
                      : GREYSCALE.dark.border
                  }`,
                width: 36,
                height: 36,
              }}
            >
              <FilterListIcon sx={{ fontSize: 20 }} />
            </IconButton>
          </Tooltip>
        )}
        {searchProps && (
          <TextField
            size="small"
            placeholder={searchProps.placeholder ?? 'Search…'}
            value={searchProps.value}
            onChange={e => searchProps.onChange(e.target.value)}
            variant="outlined"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon sx={{ fontSize: 18, color: 'text.secondary' }} />
                </InputAdornment>
              ),
            }}
            sx={{
              width: 200,
              '& .MuiOutlinedInput-root': {
                height: 36,
                borderRadius: BORDER_RADIUS.sm,
                '& fieldset': {
                  borderColor: theme =>
                    theme.palette.mode === 'light'
                      ? GREYSCALE.light.border
                      : GREYSCALE.dark.border,
                },
              },
            }}
          />
        )}
      </Box>

      {/* Middle zone: pill tabs */}
      {pillTabs && pillTabs.tabs.length > 0 && (
        <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center' }}>
          <ButtonGroup
            variant="outlined"
            size="small"
            sx={{
              '& .MuiButtonGroup-grouped': {
                borderRadius: 0, // Intentional: flush between buttons
                '&:first-of-type': {
                  borderTopLeftRadius: BORDER_RADIUS.pill,
                  borderBottomLeftRadius: BORDER_RADIUS.pill,
                },
                '&:last-of-type': {
                  borderTopRightRadius: BORDER_RADIUS.pill,
                  borderBottomRightRadius: BORDER_RADIUS.pill,
                },
                borderColor: theme =>
                  theme.palette.mode === 'light'
                    ? GREYSCALE.light.border
                    : GREYSCALE.dark.border,
              },
            }}
          >
            {pillTabs.tabs.map(tab => (
              <Button
                key={tab.value}
                onClick={() => pillTabs.onChange(tab.value)}
                sx={{
                  px: 2,
                  py: 0.5,
                  fontWeight: pillTabs.activeValue === tab.value ? 600 : 400,
                  bgcolor:
                    pillTabs.activeValue === tab.value
                      ? 'primary.dark'
                      : 'transparent',
                  color:
                    pillTabs.activeValue === tab.value
                      ? '#fff'
                      : theme =>
                          theme.palette.mode === 'light'
                            ? GREYSCALE.light.body
                            : GREYSCALE.dark.body,
                  '&:hover': {
                    bgcolor:
                      pillTabs.activeValue === tab.value
                        ? 'primary.dark'
                        : theme =>
                            theme.palette.mode === 'light'
                              ? GREYSCALE.light.surface1
                              : GREYSCALE.dark.surface1,
                  },
                }}
              >
                {tab.label}
              </Button>
            ))}
          </ButtonGroup>
        </Box>
      )}

      {/* Right zone: icon + text action buttons */}
      {rightContent ?? (
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            flexShrink: 0,
          }}
        >
          {actions.map(action => (
            <Tooltip key={action.label} title={action.tooltip ?? action.label}>
              <Button
                size="small"
                startIcon={action.icon}
                onClick={action.onClick}
                sx={{
                  color: 'text.secondary',
                  '&:hover': {
                    bgcolor: theme =>
                      theme.palette.mode === 'light'
                        ? GREYSCALE.light.surface1
                        : GREYSCALE.dark.surface1,
                  },
                }}
              >
                <Typography
                  component="span"
                  variant="bodyMReg"
                  sx={{ color: 'inherit' }}
                >
                  {action.label}
                </Typography>
              </Button>
            </Tooltip>
          ))}
        </Box>
      )}
    </Box>
  );
}

export default Toolbar;
