'use client';

import React from 'react';
import { alpha, Box, Theme, Typography } from '@mui/material';
import { getReviewBand } from '@/constants/outcomes';
import {
  DimensionItem,
  RequirementInsightColumn,
} from '../utils/requirement-insights-utils';
import { InsightsFilters } from '../types';
import {
  buildInsightsFailedTestsUrl,
  InsightsFailedTestsScope,
} from '../utils/insights-failed-tests';

/** The column the rows sit in: what a drill-down is scoped to. */
export type InsightsColumnScope = Pick<
  RequirementInsightColumn,
  'id' | 'name' | 'groupBy'
>;

/** The drill-down scope for a column; none for the "No impact" / "No parent" group. */
export function columnScope(
  column: InsightsColumnScope
): InsightsFailedTestsScope | null {
  if (column.id === null) return null;
  switch (column.groupBy) {
    case 'requirement':
      return { requirementId: column.id, requirementName: column.name };
    case 'impact':
      return { impactId: column.id, impactName: column.name };
    case 'parent':
      return {
        requirementParentId: column.id,
        requirementParentName: column.name,
      };
  }
}

function passRateTextColor(item: DimensionItem): string {
  if (item.total === 0) return 'text.secondary';
  return `${getReviewBand(item.pass_rate).colorKey}.main`;
}

function passRateRowBackground(
  item: DimensionItem,
  clickable: boolean
): (theme: Theme) => object {
  return theme => {
    if (item.total === 0) {
      return {
        bgcolor: alpha(theme.palette.grey[500], 0.06),
        ...(clickable
          ? {
              '&:hover': {
                bgcolor: alpha(theme.palette.grey[500], 0.1),
              },
            }
          : {}),
      };
    }

    const { colorKey } = getReviewBand(item.pass_rate);
    const main = theme.palette[colorKey].main;

    return {
      bgcolor: alpha(main, 0.08),
      ...(clickable
        ? {
            '&:hover': {
              bgcolor: alpha(main, 0.14),
            },
          }
        : {}),
    };
  };
}

function formatPassRate(item: DimensionItem): string {
  return item.total === 0 ? '—' : `${item.pass_rate.toFixed(0)}%`;
}

interface DimensionRowsProps {
  items: DimensionItem[];
  insightsFilters: InsightsFilters;
  column: InsightsColumnScope;
  dimension: 'metric' | 'topic';
}

function DimensionRows({
  items,
  insightsFilters,
  column,
  dimension,
}: DimensionRowsProps) {
  // The null group can't be asked for by id, so its rows only display.
  const scope = columnScope(column);
  const isClickable = (item: DimensionItem) => scope !== null && item.total > 0;

  if (items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No data
      </Typography>
    );
  }

  const openTestsForDimension = (item: DimensionItem) => {
    if (scope === null) return;
    const url = buildInsightsFailedTestsUrl(insightsFilters, {
      ...scope,
      outcome: 'all',
      ...(dimension === 'metric'
        ? { metricName: item.name }
        : { topicId: item.id, topicName: item.name }),
    });
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      {items.map(item => {
        const clickable = isClickable(item);
        return (
          <Box
            key={item.id ?? item.name}
            role={clickable ? 'button' : undefined}
            tabIndex={clickable ? 0 : undefined}
            onClick={clickable ? () => openTestsForDimension(item) : undefined}
            onKeyDown={
              clickable
                ? e => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      openTestsForDimension(item);
                    }
                  }
                : undefined
            }
            sx={[
              {
                display: 'flex',
                alignItems: 'center',
                gap: 1,
                py: 0.625,
                px: 1,
                cursor: clickable ? 'pointer' : 'default',
                borderRadius: 1,
              },
              passRateRowBackground(item, clickable),
            ]}
          >
            <Typography
              variant="body2"
              sx={{
                flex: 1,
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
              title={item.name}
            >
              {item.name}
            </Typography>
            <Typography
              variant="body2"
              fontWeight={600}
              sx={{
                flexShrink: 0,
                color: passRateTextColor(item),
              }}
            >
              {formatPassRate(item)}
            </Typography>
          </Box>
        );
      })}
    </Box>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <Typography
      variant="caption"
      fontWeight={600}
      color="text.secondary"
      sx={{
        display: 'block',
        mb: 1,
        textTransform: 'uppercase',
        letterSpacing: '0.03em',
      }}
    >
      {children}
    </Typography>
  );
}

interface RequirementListProps {
  items: DimensionItem[];
  insightsFilters: InsightsFilters;
  column: InsightsColumnScope;
}

export function RequirementMetricList({
  items,
  insightsFilters,
  column,
}: RequirementListProps) {
  if (items.length === 0) return null;

  return (
    <Box>
      <SectionLabel>Metrics</SectionLabel>
      <DimensionRows
        items={items}
        insightsFilters={insightsFilters}
        column={column}
        dimension="metric"
      />
    </Box>
  );
}

export function RequirementTopicList({
  items,
  insightsFilters,
  column,
}: RequirementListProps) {
  if (items.length === 0) return null;

  return (
    <Box>
      <SectionLabel>Topics</SectionLabel>
      <DimensionRows
        items={items}
        insightsFilters={insightsFilters}
        column={column}
        dimension="topic"
      />
    </Box>
  );
}
