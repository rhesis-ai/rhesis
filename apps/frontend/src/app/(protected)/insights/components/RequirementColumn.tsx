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
import { getReviewBand } from '@/constants/outcomes';
import { InsightsFilters } from '../types';
import { RequirementInsightColumn } from '../utils/requirement-insights-utils';
import {
  RequirementMetricList,
  RequirementTopicList,
} from './RequirementDimensionLists';
import InsightsImpactDot from './InsightsImpactDot';

const MAX_CHILDREN_SHOWN = 3;

interface RequirementColumnProps {
  column: RequirementInsightColumn;
  insightsFilters: InsightsFilters;
  loading?: boolean;
  expanded?: boolean;
}

export default function RequirementColumn({
  column,
  insightsFilters,
  loading = false,
  expanded = false,
}: RequirementColumnProps) {
  const noTests = column.overall.total === 0;
  // Like the requirement cards: "● Safety impact" under the name. Grouped by
  // impact the name already is the impact, so it gets no line and no dot.
  const impactLine = column.groupBy === 'impact' ? null : column.impact;
  const shownChildren = column.children.slice(0, MAX_CHILDREN_SHOWN);
  const hiddenChildren = column.children.slice(MAX_CHILDREN_SHOWN);
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
        <Box
          sx={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            alignItems: 'flex-start',
            gap: 1,
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography
              variant="subtitle1"
              fontWeight={700}
              title={column.name}
              sx={{
                lineHeight: 1.3,
                minHeight:
                  impactLine || shownChildren.length > 0 ? undefined : '2.6em',
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}
            >
              {column.name}
            </Typography>
            {shownChildren.length > 0 ? (
              <Box
                component="ul"
                aria-label="Requirements in this group"
                sx={{
                  m: 0,
                  mt: 0.75,
                  p: 0,
                  listStyle: 'none',
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 0.5,
                }}
              >
                {shownChildren.map(child => (
                  <li key={child}>
                    <Chip
                      label={child}
                      size="small"
                      variant="outlined"
                      sx={{ maxWidth: '100%' }}
                    />
                  </li>
                ))}
                {hiddenChildren.length > 0 ? (
                  <li>
                    <Tooltip title={hiddenChildren.join(', ')} arrow>
                      <Chip
                        label={`+${hiddenChildren.length} more`}
                        size="small"
                        variant="outlined"
                        tabIndex={0}
                      />
                    </Tooltip>
                  </li>
                ) : null}
              </Box>
            ) : null}
            {impactLine ? (
              <Box
                component="span"
                sx={{
                  mt: 0.5,
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 0.75,
                  fontSize: 13,
                  lineHeight: '20px',
                  color: 'text.secondary',
                }}
              >
                <InsightsImpactDot impact={impactLine} decorative />
                {impactLine} impact
              </Box>
            ) : null}
          </Box>
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
              <RequirementMetricList
                items={column.metrics}
                insightsFilters={insightsFilters}
                column={column}
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
              <RequirementTopicList
                items={column.topics}
                insightsFilters={insightsFilters}
                column={column}
              />
            )}
          </Box>
        </Box>
      </Collapse>
    </Paper>
  );
}
