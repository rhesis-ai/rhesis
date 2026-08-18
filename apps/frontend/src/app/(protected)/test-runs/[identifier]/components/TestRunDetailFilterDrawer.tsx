'use client';

import * as React from 'react';
import {
  Box,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Tooltip,
  Typography,
} from '@mui/material';
import RadioButtonUncheckedIcon from '@mui/icons-material/RadioButtonUnchecked';
import VisibilityOutlinedIcon from '@mui/icons-material/VisibilityOutlined';
import CheckCircleOutlineIcon from '@mui/icons-material/CheckCircleOutline';
import BlockOutlinedIcon from '@mui/icons-material/BlockOutlined';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';
import type { MetricOutcomeFilter } from './TestRunFilterBar';

export type TestRunDetailDrawerFilters = {
  overruleFilter: 'all' | 'overruled' | 'original' | 'conflicting';
  commentFilter: 'all' | 'with_comments' | 'without_comments' | 'range';
  taskFilter: 'all' | 'with_tasks' | 'without_tasks' | 'range';
  metricFilters: Record<string, MetricOutcomeFilter>;
  selectedRequirements: string[];
};

export const EMPTY_TEST_RUN_DETAIL_DRAWER_FILTERS: TestRunDetailDrawerFilters =
  {
    overruleFilter: 'all',
    commentFilter: 'all',
    taskFilter: 'all',
    metricFilters: {},
    selectedRequirements: [],
  };

export function extractDetailDrawerFilters(filter: {
  overruleFilter: TestRunDetailDrawerFilters['overruleFilter'];
  commentFilter: TestRunDetailDrawerFilters['commentFilter'];
  taskFilter: TestRunDetailDrawerFilters['taskFilter'];
  metricFilters: Record<string, MetricOutcomeFilter>;
  selectedRequirements: string[];
}): TestRunDetailDrawerFilters {
  return {
    overruleFilter: filter.overruleFilter,
    commentFilter: filter.commentFilter,
    taskFilter: filter.taskFilter,
    metricFilters: filter.metricFilters,
    selectedRequirements: filter.selectedRequirements,
  };
}

export function hasActiveTestRunDetailDrawerFilters(
  filters: TestRunDetailDrawerFilters
): boolean {
  return (
    filters.overruleFilter !== 'all' ||
    filters.commentFilter !== 'all' ||
    filters.taskFilter !== 'all' ||
    Object.keys(filters.metricFilters).length > 0 ||
    filters.selectedRequirements.length > 0
  );
}

export function countActiveTestRunDetailDrawerFilters(
  filters: TestRunDetailDrawerFilters
): number {
  return (
    (filters.overruleFilter !== 'all' ? 1 : 0) +
    (filters.commentFilter !== 'all' ? 1 : 0) +
    (filters.taskFilter !== 'all' ? 1 : 0) +
    Object.keys(filters.metricFilters).length +
    filters.selectedRequirements.length
  );
}

const REVIEW_STATUS_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'overruled', label: 'Reviewed' },
  { value: 'original', label: 'Not Reviewed' },
  { value: 'conflicting', label: 'Conflicting' },
] as const;

const COMMENT_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'with_comments', label: 'With' },
  { value: 'without_comments', label: 'Without' },
] as const;

const TASK_OPTIONS = [
  { value: 'all', label: 'All' },
  { value: 'with_tasks', label: 'With' },
  { value: 'without_tasks', label: 'Without' },
] as const;

// Icon-only pills for per-metric rows (labels would be too wide next to a
// metric name) -- MetricLegend below spells out what each icon means once.
const METRIC_OUTCOME_OPTIONS = [
  {
    value: 'all',
    label: 'All',
    icon: <RadioButtonUncheckedIcon fontSize="small" />,
  },
  {
    value: 'evaluated',
    label: 'Evaluated',
    icon: <VisibilityOutlinedIcon fontSize="small" />,
  },
  {
    value: 'passed',
    label: 'Passed',
    icon: <CheckCircleOutlineIcon fontSize="small" />,
  },
  {
    value: 'failed',
    label: 'Failed',
    icon: <BlockOutlinedIcon fontSize="small" />,
  },
] as const;

interface CompactSegmentedPillsProps {
  tabs: { value: string; label: string }[];
  activeValue: string;
  onChange: (value: string) => void;
}

/** Right-aligned segmented pills for drawer sub-rows (Activity). */
function CompactSegmentedPills({
  tabs,
  activeValue,
  onChange,
}: CompactSegmentedPillsProps) {
  return (
    <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
      {tabs.map(({ value, label }, idx, arr) => {
        const isSelected = activeValue === value;
        const isFirst = idx === 0;
        const isLast = idx === arr.length - 1;

        return (
          <Box
            key={value}
            component="button"
            type="button"
            onClick={() => onChange(value)}
            sx={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              px: '12px',
              py: '6px',
              fontSize: 13,
              fontWeight: 700,
              lineHeight: '20px',
              cursor: 'pointer',
              border: '1px solid',
              borderColor: 'primary.main',
              borderLeft: isFirst ? '1px solid' : 'none',
              borderRight: isLast ? '1px solid' : 'none',
              borderRadius: isFirst
                ? '999px 0 0 999px'
                : isLast
                  ? '0 999px 999px 0'
                  : 0,
              bgcolor: isSelected ? 'primary.main' : 'transparent',
              color: theme =>
                isSelected
                  ? theme.palette.primary.contrastText
                  : theme.palette.primary.main,
              whiteSpace: 'nowrap',
              '&:hover': {
                bgcolor: isSelected
                  ? 'primary.dark'
                  : theme => `${theme.palette.primary.main}0f`,
              },
            }}
          >
            {label}
          </Box>
        );
      })}
    </Box>
  );
}

interface ActivityRowProps {
  label: string;
  tabs: { value: string; label: string }[];
  activeValue: string;
  onChange: (value: string) => void;
}

function ActivityFilterRow({
  label,
  tabs,
  activeValue,
  onChange,
}: ActivityRowProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 2,
      }}
    >
      <Typography
        sx={{
          fontSize: 14,
          color: theme => theme.palette.greyscale.body,
          flexShrink: 0,
        }}
      >
        {label}
      </Typography>
      <CompactSegmentedPills
        tabs={tabs}
        activeValue={activeValue}
        onChange={onChange}
      />
    </Box>
  );
}

/** One-time key explaining the icon-only pills used on each metric row below. */
function MetricOutcomeLegend() {
  return (
    <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 0.5 }}>
      {METRIC_OUTCOME_OPTIONS.map(({ value, label, icon }) => (
        <Box
          key={value}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 0.5,
            color: theme => theme.palette.greyscale.body,
          }}
        >
          {icon}
          <Typography sx={{ fontSize: 12 }}>{label}</Typography>
        </Box>
      ))}
    </Box>
  );
}

interface MetricOutcomeRowProps {
  label: string;
  activeValue: string;
  onChange: (value: string) => void;
}

/** Metric name plus an icon-only segmented pill (All/Evaluated/Passed/Failed)
 * -- icons keep this compact next to a long metric name; MetricOutcomeLegend
 * spells out what each one means once, at the top of the section. */
function MetricOutcomeRow({
  label,
  activeValue,
  onChange,
}: MetricOutcomeRowProps) {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: 1.5,
      }}
    >
      <Typography
        title={label}
        sx={{
          fontSize: 14,
          color: theme => theme.palette.greyscale.body,
          minWidth: 0,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {label}
      </Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        {METRIC_OUTCOME_OPTIONS.map(
          ({ value, label: optionLabel, icon }, idx, arr) => {
            const isSelected = activeValue === value;
            const isFirst = idx === 0;
            const isLast = idx === arr.length - 1;
            return (
              <Tooltip key={value} title={optionLabel}>
                <Box
                  component="button"
                  type="button"
                  aria-label={optionLabel}
                  onClick={() => onChange(value)}
                  sx={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 30,
                    height: 28,
                    cursor: 'pointer',
                    border: '1px solid',
                    borderColor: 'primary.main',
                    borderLeft: isFirst ? '1px solid' : 'none',
                    borderRight: isLast ? '1px solid' : 'none',
                    borderRadius: isFirst
                      ? '999px 0 0 999px'
                      : isLast
                        ? '0 999px 999px 0'
                        : 0,
                    bgcolor: isSelected ? 'primary.main' : 'transparent',
                    color: theme =>
                      isSelected
                        ? theme.palette.primary.contrastText
                        : theme.palette.primary.main,
                    '&:hover': {
                      bgcolor: isSelected
                        ? 'primary.dark'
                        : theme => `${theme.palette.primary.main}0f`,
                    },
                  }}
                >
                  {icon}
                </Box>
              </Tooltip>
            );
          }
        )}
      </Box>
    </Box>
  );
}

interface TestRunDetailFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestRunDetailDrawerFilters;
  availableRequirements: Array<{ id: string; name: string }>;
  availableMetrics: Array<{ name: string; description?: string }>;
  onApply: (filters: TestRunDetailDrawerFilters) => void;
}

export default function TestRunDetailFilterDrawer({
  open,
  onClose,
  filters,
  availableRequirements,
  availableMetrics,
  onApply,
}: TestRunDetailFilterDrawerProps) {
  const { draft, setDraft, handleReset, handleApply } = useFilterDrawerDraft(
    open,
    filters,
    EMPTY_TEST_RUN_DETAIL_DRAWER_FILTERS,
    onApply,
    onClose
  );

  const setMetricOutcome = (metricName: string, value: string) => {
    setDraft(prev => {
      const metricFilters = { ...prev.metricFilters };
      if (value === 'all') {
        delete metricFilters[metricName];
      } else {
        metricFilters[metricName] = value as MetricOutcomeFilter;
      }
      return { ...prev, metricFilters };
    });
  };

  const toggleRequirement = (requirementId: string) => {
    setDraft(prev => ({
      ...prev,
      selectedRequirements: prev.selectedRequirements.includes(requirementId)
        ? prev.selectedRequirements.filter(id => id !== requirementId)
        : [...prev.selectedRequirements, requirementId],
    }));
  };

  return (
    <FilterDrawerShell
      open={open}
      onClose={onClose}
      onReset={handleReset}
      onApply={handleApply}
    >
      <FilterSection title="Review Status">
        <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
          {REVIEW_STATUS_OPTIONS.map(option => (
            <Box
              key={option.value}
              component="button"
              type="button"
              onClick={() =>
                setDraft(prev => ({
                  ...prev,
                  overruleFilter: option.value,
                }))
              }
              sx={filterChipSx(draft.overruleFilter === option.value)}
            >
              {option.label}
            </Box>
          ))}
        </Box>
      </FilterSection>

      <FilterSection title="Activity">
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
          <ActivityFilterRow
            label="Comments"
            tabs={[...COMMENT_OPTIONS]}
            activeValue={draft.commentFilter}
            onChange={value =>
              setDraft(prev => ({
                ...prev,
                commentFilter:
                  value as TestRunDetailDrawerFilters['commentFilter'],
              }))
            }
          />
          <ActivityFilterRow
            label="Tasks"
            tabs={[...TASK_OPTIONS]}
            activeValue={draft.taskFilter}
            onChange={value =>
              setDraft(prev => ({
                ...prev,
                taskFilter: value as TestRunDetailDrawerFilters['taskFilter'],
              }))
            }
          />
        </Box>
      </FilterSection>

      {availableMetrics.length > 0 && (
        <FilterSection title="Metrics Evaluated">
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
            <MetricOutcomeLegend />
            {availableMetrics.map(metric => (
              <MetricOutcomeRow
                key={metric.name}
                label={metric.name}
                activeValue={draft.metricFilters[metric.name] ?? 'all'}
                onChange={value => setMetricOutcome(metric.name, value)}
              />
            ))}
          </Box>
        </FilterSection>
      )}

      {availableRequirements.length > 0 && (
        <FilterSection title="Requirements">
          <FormGroup>
            {availableRequirements.map(requirement => (
              <FormControlLabel
                key={requirement.id}
                control={
                  <Checkbox
                    checked={draft.selectedRequirements.includes(
                      requirement.id
                    )}
                    onChange={() => toggleRequirement(requirement.id)}
                    size="small"
                  />
                }
                label={
                  <Typography sx={{ fontSize: 14 }}>
                    {requirement.name}
                  </Typography>
                }
                sx={{ ml: 0, mb: 0.5 }}
              />
            ))}
          </FormGroup>
        </FilterSection>
      )}
    </FilterDrawerShell>
  );
}
