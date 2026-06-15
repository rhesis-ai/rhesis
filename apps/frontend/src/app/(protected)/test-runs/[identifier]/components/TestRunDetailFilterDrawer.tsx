'use client';

import * as React from 'react';
import {
  Box,
  Checkbox,
  FormControlLabel,
  FormGroup,
  Typography,
} from '@mui/material';
import {
  FilterDrawerShell,
  FilterSection,
  filterChipSx,
  useFilterDrawerDraft,
} from '@/components/common/FilterDrawer';

export type TestRunDetailDrawerFilters = {
  overruleFilter: 'all' | 'overruled' | 'original' | 'conflicting';
  commentFilter: 'all' | 'with_comments' | 'without_comments' | 'range';
  taskFilter: 'all' | 'with_tasks' | 'without_tasks' | 'range';
  selectedMetrics: string[];
  selectedBehaviors: string[];
};

export const EMPTY_TEST_RUN_DETAIL_DRAWER_FILTERS: TestRunDetailDrawerFilters =
  {
    overruleFilter: 'all',
    commentFilter: 'all',
    taskFilter: 'all',
    selectedMetrics: [],
    selectedBehaviors: [],
  };

export function extractDetailDrawerFilters(filter: {
  overruleFilter: TestRunDetailDrawerFilters['overruleFilter'];
  commentFilter: TestRunDetailDrawerFilters['commentFilter'];
  taskFilter: TestRunDetailDrawerFilters['taskFilter'];
  selectedMetrics: string[];
  selectedBehaviors: string[];
}): TestRunDetailDrawerFilters {
  return {
    overruleFilter: filter.overruleFilter,
    commentFilter: filter.commentFilter,
    taskFilter: filter.taskFilter,
    selectedMetrics: filter.selectedMetrics,
    selectedBehaviors: filter.selectedBehaviors,
  };
}

export function hasActiveTestRunDetailDrawerFilters(
  filters: TestRunDetailDrawerFilters
): boolean {
  return (
    filters.overruleFilter !== 'all' ||
    filters.commentFilter !== 'all' ||
    filters.taskFilter !== 'all' ||
    filters.selectedMetrics.length > 0 ||
    filters.selectedBehaviors.length > 0
  );
}

export function countActiveTestRunDetailDrawerFilters(
  filters: TestRunDetailDrawerFilters
): number {
  return (
    (filters.overruleFilter !== 'all' ? 1 : 0) +
    (filters.commentFilter !== 'all' ? 1 : 0) +
    (filters.taskFilter !== 'all' ? 1 : 0) +
    filters.selectedMetrics.length +
    filters.selectedBehaviors.length
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
              color: isSelected ? '#fff' : 'primary.main',
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

interface TestRunDetailFilterDrawerProps {
  open: boolean;
  onClose: () => void;
  filters: TestRunDetailDrawerFilters;
  availableBehaviors: Array<{ id: string; name: string }>;
  availableMetrics: Array<{ name: string; description?: string }>;
  onApply: (filters: TestRunDetailDrawerFilters) => void;
}

export default function TestRunDetailFilterDrawer({
  open,
  onClose,
  filters,
  availableBehaviors,
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

  const toggleMetric = (metricName: string) => {
    setDraft(prev => ({
      ...prev,
      selectedMetrics: prev.selectedMetrics.includes(metricName)
        ? prev.selectedMetrics.filter(name => name !== metricName)
        : [...prev.selectedMetrics, metricName],
    }));
  };

  const toggleBehavior = (behaviorId: string) => {
    setDraft(prev => ({
      ...prev,
      selectedBehaviors: prev.selectedBehaviors.includes(behaviorId)
        ? prev.selectedBehaviors.filter(id => id !== behaviorId)
        : [...prev.selectedBehaviors, behaviorId],
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
        <FilterSection title="Metrics">
          <FormGroup>
            {availableMetrics.map(metric => (
              <FormControlLabel
                key={metric.name}
                control={
                  <Checkbox
                    checked={draft.selectedMetrics.includes(metric.name)}
                    onChange={() => toggleMetric(metric.name)}
                    size="small"
                  />
                }
                label={
                  <Typography sx={{ fontSize: 14 }}>{metric.name}</Typography>
                }
                sx={{ ml: 0, mb: 0.5 }}
              />
            ))}
          </FormGroup>
        </FilterSection>
      )}

      {availableBehaviors.length > 0 && (
        <FilterSection title="Behaviors">
          <FormGroup>
            {availableBehaviors.map(behavior => (
              <FormControlLabel
                key={behavior.id}
                control={
                  <Checkbox
                    checked={draft.selectedBehaviors.includes(behavior.id)}
                    onChange={() => toggleBehavior(behavior.id)}
                    size="small"
                  />
                }
                label={
                  <Typography sx={{ fontSize: 14 }}>{behavior.name}</Typography>
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
