'use client';

import React from 'react';
import {
  Box,
  Chip,
  Collapse,
  Divider,
  Paper,
  Skeleton,
  Tooltip,
  Typography,
} from '@mui/material';
import { getReviewBand } from '@/app/(protected)/test-runs/[identifier]/components/test-run-summary-utils';
import { InsightsFilters } from '../types';
import { BehaviorInsightColumn } from '../utils/behavior-insights-utils';
import {
  BehaviorMetricList,
  BehaviorTopicList,
} from './BehaviorDimensionLists';

interface BehaviorColumnProps {
  column: BehaviorInsightColumn;
  insightsFilters: InsightsFilters;
  loading?: boolean;
  expanded?: boolean;
}

export default function BehaviorColumn({
  column,
  insightsFilters,
  loading = false,
  expanded = false,
}: BehaviorColumnProps) {
  const noTests = column.overall.total === 0;
  const hasMetrics = column.metrics.length > 0;
  const hasTopics = column.topics.length > 0;
  const isExpandable = !noTests && (hasMetrics || hasTopics);

  if (loading) {
    return (
      <Paper
        variant="outlined"
        sx={{
          p: 2,
          borderRadius: 2,
          width: '100%',
          height: '100%',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
          <Skeleton variant="circular" width={28} height={28} />
          <Box sx={{ flex: 1 }}>
            <Skeleton width="55%" height={40} />
          </Box>
          <Skeleton width={48} height={28} />
        </Box>
      </Paper>
    );
  }

  const passCountLabel = noTests
    ? 'No tests run'
    : `${column.overall.passed}/${column.overall.total} passed`;

  return (
    <Paper
      variant="outlined"
      sx={{
        borderRadius: 2,
        width: '100%',
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}
    >
      <Box
        sx={{
          flex: isExpandable && expanded ? '0 0 auto' : 1,
          display: 'flex',
          alignItems: 'flex-start',
          gap: 0.5,
          p: 2,
        }}
      >
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography
            variant="subtitle1"
            fontWeight={700}
            title={column.name}
            sx={{
              lineHeight: 1.3,
              minHeight: '2.6em',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {column.name}
          </Typography>
        </Box>

        <Tooltip title={passCountLabel} placement="top" arrow>
          <Chip
            label={
              noTests ? 'No tests' : `${column.overall.pass_rate.toFixed(0)}%`
            }
            size="small"
            color={
              noTests
                ? 'default'
                : getReviewBand(column.overall.pass_rate).colorKey
            }
            variant={noTests ? 'outlined' : 'filled'}
            onClick={e => e.stopPropagation()}
            sx={{ fontWeight: 600, flexShrink: 0, cursor: 'default' }}
          />
        </Tooltip>
      </Box>

      <Collapse
        in={expanded && isExpandable}
        unmountOnExit
        sx={{
          flex: expanded && isExpandable ? '1 1 auto' : '0 0 auto',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          '& .MuiCollapse-wrapper': {
            display: 'flex',
            flex: 1,
            minHeight: 0,
          },
          '& .MuiCollapse-wrapperInner': {
            display: 'flex',
            flex: 1,
            flexDirection: 'column',
            minHeight: 0,
          },
        }}
      >
        <Box
          sx={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            px: 2,
            pb: 2,
            pt: 0,
            borderTop: 1,
            borderColor: 'divider',
          }}
        >
          <Box
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2,
              pt: 1.5,
            }}
          >
            {hasMetrics && (
              <BehaviorMetricList
                items={column.metrics}
                insightsFilters={insightsFilters}
                behaviorId={column.id}
                behaviorName={column.name}
              />
            )}
            {hasMetrics && hasTopics && (
              <Divider
                sx={{
                  width: '55%',
                  mx: 'auto',
                  my: 0.25,
                  borderColor: 'divider',
                }}
              />
            )}
            {hasTopics && (
              <BehaviorTopicList
                items={column.topics}
                insightsFilters={insightsFilters}
                behaviorId={column.id}
                behaviorName={column.name}
              />
            )}
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
}
