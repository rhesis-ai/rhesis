'use client';

import React, { useState, useEffect } from 'react';
import {
  Drawer,
  Box,
  Typography,
  IconButton,
  Button,
  Checkbox,
  Radio,
  RadioGroup,
  FormControlLabel,
  FormGroup,
  Switch,
  Chip,
  Collapse,
  Link,
  Divider,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import KeyboardArrowUpIcon from '@mui/icons-material/KeyboardArrowUp';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import { useTheme } from '@mui/material/styles';

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

export interface FilterSection {
  id: string;
  title: string;
  type: 'checkbox' | 'radio' | 'toggle' | 'badges';
  label?: string;
  options: FilterOption[];
  infoText?: string;
  showAllThreshold?: number;
  defaultCollapsed?: boolean;
}

export type FilterValues = Record<string, string[]>;

interface FilterDrawerProps {
  open: boolean;
  onClose: () => void;
  sections: FilterSection[];
  values: FilterValues;
  onApply: (values: FilterValues) => void;
  onReset: () => void;
  title?: string;
  applyLabel?: string;
  resetLabel?: string;
}

export default function FilterDrawer({
  open,
  onClose,
  sections,
  values,
  onApply,
  onReset,
  title = 'Filter',
  applyLabel = 'Apply',
  resetLabel = 'Reset',
}: FilterDrawerProps) {
  const theme = useTheme();
  const [localValues, setLocalValues] = useState<FilterValues>(values);
  const [collapsedSections, setCollapsedSections] = useState<
    Record<string, boolean>
  >({});
  const [expandedSections, setExpandedSections] = useState<
    Record<string, boolean>
  >({});

  useEffect(() => {
    setLocalValues(values);
  }, [values, open]);

  useEffect(() => {
    const initial: Record<string, boolean> = {};
    sections.forEach(section => {
      if (section.defaultCollapsed) {
        initial[section.id] = true;
      }
    });
    setCollapsedSections(initial);
  }, [sections]);

  const toggleCollapse = (sectionId: string) => {
    setCollapsedSections(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

  const toggleShowAll = (sectionId: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

  const handleCheckboxChange = (sectionId: string, optionValue: string) => {
    setLocalValues(prev => {
      const current = prev[sectionId] || [];
      const next = current.includes(optionValue)
        ? current.filter(v => v !== optionValue)
        : [...current, optionValue];
      return { ...prev, [sectionId]: next };
    });
  };

  const handleRadioChange = (sectionId: string, optionValue: string) => {
    setLocalValues(prev => ({ ...prev, [sectionId]: [optionValue] }));
  };

  const handleToggleChange = (sectionId: string, optionValue: string) => {
    setLocalValues(prev => {
      const current = prev[sectionId] || [];
      const next = current.includes(optionValue)
        ? current.filter(v => v !== optionValue)
        : [...current, optionValue];
      return { ...prev, [sectionId]: next };
    });
  };

  const handleBadgeClick = (sectionId: string, optionValue: string) => {
    setLocalValues(prev => {
      const current = prev[sectionId] || [];
      const next = current.includes(optionValue)
        ? current.filter(v => v !== optionValue)
        : [...current, optionValue];
      return { ...prev, [sectionId]: next };
    });
  };

  const handleApply = () => {
    onApply(localValues);
    onClose();
  };

  const handleReset = () => {
    const empty: FilterValues = {};
    sections.forEach(s => {
      empty[s.id] = [];
    });
    setLocalValues(empty);
    onReset();
    onClose();
  };

  const renderSection = (section: FilterSection) => {
    const isCollapsed = collapsedSections[section.id] ?? false;
    const isExpanded = expandedSections[section.id] ?? false;
    const threshold = section.showAllThreshold ?? Infinity;
    const visibleOptions =
      isExpanded || section.options.length <= threshold
        ? section.options
        : section.options.slice(0, threshold);
    const hasMore = section.options.length > threshold;
    const selected = localValues[section.id] || [];

    return (
      <Box
        key={section.id}
        sx={{
          borderTop: `1px solid ${theme.greyscale.border.disabled}`,
          pt: 2.5,
          display: 'flex',
          flexDirection: 'column',
          gap: 2.5,
        }}
      >
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            cursor: 'pointer',
          }}
          onClick={() => toggleCollapse(section.id)}
        >
          <Typography
            sx={{
              fontSize: 16,
              fontWeight: 700,
              lineHeight: '24px',
              color: theme.greyscale.text.title,
            }}
          >
            {section.title}
          </Typography>
          {isCollapsed ? (
            <KeyboardArrowDownIcon
              sx={{ fontSize: 20, color: theme.greyscale.text.subtitle }}
            />
          ) : (
            <KeyboardArrowUpIcon
              sx={{ fontSize: 20, color: theme.greyscale.text.subtitle }}
            />
          )}
        </Box>

        <Collapse in={!isCollapsed}>
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
            {section.label && (
              <Typography
                sx={{
                  fontSize: 14,
                  lineHeight: '22px',
                  color: theme.greyscale.text.body,
                }}
              >
                {section.label}
              </Typography>
            )}

            {section.type === 'checkbox' && (
              <FormGroup>
                {visibleOptions.map(option => (
                  <Box
                    key={option.value}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      height: 38,
                    }}
                  >
                    <FormControlLabel
                      control={
                        <Checkbox
                          size="small"
                          checked={selected.includes(option.value)}
                          onChange={() =>
                            handleCheckboxChange(section.id, option.value)
                          }
                          sx={{ py: 0.5 }}
                        />
                      }
                      label={
                        <Typography sx={{ fontSize: 14, lineHeight: '22px' }}>
                          {option.label}
                        </Typography>
                      }
                      sx={{ mr: 0 }}
                    />
                    {option.count !== undefined && (
                      <Typography
                        sx={{
                          fontSize: 14,
                          lineHeight: '22px',
                          color: theme.greyscale.text.subtitle,
                        }}
                      >
                        {option.count}
                      </Typography>
                    )}
                  </Box>
                ))}
              </FormGroup>
            )}

            {section.type === 'radio' && (
              <RadioGroup
                value={selected[0] || ''}
                onChange={e => handleRadioChange(section.id, e.target.value)}
              >
                {visibleOptions.map(option => (
                  <Box
                    key={option.value}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      height: 38,
                    }}
                  >
                    <FormControlLabel
                      value={option.value}
                      control={<Radio size="small" sx={{ py: 0.5 }} />}
                      label={
                        <Typography sx={{ fontSize: 14, lineHeight: '22px' }}>
                          {option.label}
                        </Typography>
                      }
                      sx={{ mr: 0 }}
                    />
                    {option.count !== undefined && (
                      <Typography
                        sx={{
                          fontSize: 14,
                          lineHeight: '22px',
                          color: theme.greyscale.text.subtitle,
                        }}
                      >
                        {option.count}
                      </Typography>
                    )}
                  </Box>
                ))}
              </RadioGroup>
            )}

            {section.type === 'toggle' && (
              <Box sx={{ display: 'flex', flexDirection: 'column' }}>
                {visibleOptions.map(option => (
                  <Box
                    key={option.value}
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      height: 38,
                    }}
                  >
                    <Typography sx={{ fontSize: 14, lineHeight: '22px' }}>
                      {option.label}
                    </Typography>
                    <Switch
                      size="small"
                      checked={selected.includes(option.value)}
                      onChange={() =>
                        handleToggleChange(section.id, option.value)
                      }
                    />
                  </Box>
                ))}
              </Box>
            )}

            {section.type === 'badges' && (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                {visibleOptions.map(option => {
                  const isSelected = selected.includes(option.value);
                  return (
                    <Chip
                      key={option.value}
                      label={option.label}
                      size="small"
                      variant={isSelected ? 'filled' : 'outlined'}
                      color={isSelected ? 'primary' : 'default'}
                      onClick={() => handleBadgeClick(section.id, option.value)}
                      sx={{
                        borderRadius: '4px',
                        fontWeight: isSelected ? 600 : 400,
                      }}
                    />
                  );
                })}
              </Box>
            )}

            {section.infoText && (
              <Typography
                sx={{
                  fontSize: 12,
                  lineHeight: '18px',
                  color: 'text.secondary',
                  pt: 0.375,
                }}
              >
                {section.infoText}
              </Typography>
            )}

            {hasMore && (
              <Link
                component="button"
                onClick={() => toggleShowAll(section.id)}
                underline="always"
                sx={{
                  fontSize: 14,
                  lineHeight: '22px',
                  color: theme.greyscale.text.body,
                  cursor: 'pointer',
                  alignSelf: 'flex-start',
                }}
              >
                {isExpanded ? 'Show less' : 'Show all'}
              </Link>
            )}
          </Box>
        </Collapse>
      </Box>
    );
  };

  return (
    <Drawer
      anchor="left"
      open={open}
      onClose={onClose}
      sx={{
        '& .MuiBackdrop-root': {
          backgroundColor: 'rgba(127, 138, 155, 0.8)',
        },
      }}
      PaperProps={{
        sx: {
          width: 430,
          maxWidth: '100vw',
          display: 'flex',
          flexDirection: 'column',
        },
      }}
    >
      <Box
        sx={{
          flex: 1,
          overflow: 'auto',
          p: 3.75,
          display: 'flex',
          flexDirection: 'column',
          gap: 3.75,
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
              lineHeight: 1.1,
              color: '#21272A',
            }}
          >
            {title}
          </Typography>
          <IconButton onClick={onClose} size="small">
            <CloseIcon />
          </IconButton>
        </Box>

        {/* Filter sections */}
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            gap: 5,
          }}
        >
          {sections.map(renderSection)}
        </Box>
      </Box>

      {/* Footer */}
      <Divider />
      <Box
        sx={{
          display: 'flex',
          gap: 1.5,
          p: 3.75,
          pt: 2.5,
        }}
      >
        <Button variant="outlined" onClick={handleReset} size="small">
          {resetLabel}
        </Button>
        <Button variant="contained" onClick={handleApply} size="small">
          {applyLabel}
        </Button>
      </Box>
    </Drawer>
  );
}
