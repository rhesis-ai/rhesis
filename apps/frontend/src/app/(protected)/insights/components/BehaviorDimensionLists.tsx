'use client';

import React from 'react';
import { alpha, Box, Theme, Typography } from '@mui/material';
import { getReviewBand } from '@/app/(protected)/test-runs/[identifier]/components/test-run-summary-utils';
import { DimensionItem } from '../utils/behavior-insights-utils';
import { InsightsFilters } from '../types';
import {
  buildInsightsFailedTestsUrl,
  InsightsFailedTestsScope,
} from '../utils/insights-failed-tests';

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

function isClickable(item: DimensionItem): boolean {
  return item.total > 0;
}

interface DimensionRowsProps {
  items: DimensionItem[];
  insightsFilters: InsightsFilters;
  behaviorId: string;
  behaviorName: string;
  dimension: 'metric' | 'topic';
}

function DimensionRows({
  items,
  insightsFilters,
  behaviorId,
  behaviorName,
  dimension,
}: DimensionRowsProps) {
  if (items.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No data
      </Typography>
    );
  }

  const openTestsForDimension = (item: DimensionItem) => {
    const scope: InsightsFailedTestsScope = {
      behaviorId,
      behaviorName,
      outcome: 'all',
      ...(dimension === 'metric'
        ? { metricName: item.name }
        : { topicName: item.name }),
    };
    const url = buildInsightsFailedTestsUrl(insightsFilters, scope);
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
      {items.map(item => {
        const clickable = isClickable(item);
        return (
          <Box
            key={item.name}
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

interface BehaviorMetricListProps {
  items: DimensionItem[];
  insightsFilters: InsightsFilters;
  behaviorId: string;
  behaviorName: string;
}

export function BehaviorMetricList({
  items,
  insightsFilters,
  behaviorId,
  behaviorName,
}: BehaviorMetricListProps) {
  if (items.length === 0) return null;

  return (
    <Box>
      <SectionLabel>Metrics</SectionLabel>
      <DimensionRows
        items={items}
        insightsFilters={insightsFilters}
        behaviorId={behaviorId}
        behaviorName={behaviorName}
        dimension="metric"
      />
    </Box>
  );
}

interface BehaviorTopicListProps {
  items: DimensionItem[];
  insightsFilters: InsightsFilters;
  behaviorId: string;
  behaviorName: string;
}

export function BehaviorTopicList({
  items,
  insightsFilters,
  behaviorId,
  behaviorName,
}: BehaviorTopicListProps) {
  if (items.length === 0) return null;

  return (
    <Box>
      <SectionLabel>Topics</SectionLabel>
      <DimensionRows
        items={items}
        insightsFilters={insightsFilters}
        behaviorId={behaviorId}
        behaviorName={behaviorName}
        dimension="topic"
      />
    </Box>
  );
}
