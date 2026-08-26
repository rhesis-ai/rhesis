'use client';

import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Box,
  Chip,
  CircularProgress,
  Grid,
  Stack,
  Typography,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import type {
  InsightsQueryResponse,
  InsightsRow,
} from '@/utils/api-client/interfaces/insights';
import {
  rowToPassFailStats,
  type DimensionItem,
} from '@/app/(protected)/insights/utils/requirement-insights-utils';
import { fetchAllTestResults } from '../../hooks/useTestRunDetailData';
import {
  computeReviewSummary,
  getReviewBand,
  type ReviewSummary,
} from '../test-run-summary-utils';

interface BreakdownsDrawerProps {
  testRunId: string;
}

function namedDimensionItems(
  rows: InsightsRow[],
  nameKey: string
): DimensionItem[] {
  return rows
    .flatMap(row => {
      const name = row[nameKey];
      if (typeof name !== 'string' || !name) return [];
      return [{ name, ...rowToPassFailStats(row) }];
    })
    .sort((a, b) => a.pass_rate - b.pass_rate);
}

function BandChip({ passRate }: { passRate: number }) {
  const band = getReviewBand(passRate);
  return (
    <Chip
      label={band.label}
      size="small"
      color={band.colorKey}
      sx={{ fontWeight: 500 }}
    />
  );
}

function ReviewsSummary({ summary }: { summary: ReviewSummary }) {
  return (
    <Box>
      <Typography variant="h4" fontWeight={600} sx={{ mb: 1 }}>
        {summary.headline}
      </Typography>
      <Typography variant="body2" color="text.secondary">
        {summary.subtitle}
      </Typography>
    </Box>
  );
}

function DimensionList({ items }: { items: DimensionItem[] }) {
  return (
    <Stack spacing={0.5}>
      {items.map(item => (
        <Box
          key={item.name}
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            py: 0.75,
            borderBottom: 1,
            borderColor: 'divider',
            '&:last-child': { borderBottom: 0 },
          }}
        >
          <Typography
            variant="body2"
            sx={{
              flex: 1,
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
            color="text.secondary"
            sx={{ whiteSpace: 'nowrap', minWidth: 48, textAlign: 'right' }}
          >
            {item.total} tests
          </Typography>
          <Typography
            variant="body2"
            fontWeight={600}
            sx={{ whiteSpace: 'nowrap', minWidth: 52, textAlign: 'right' }}
          >
            {item.pass_rate.toFixed(1)}%
          </Typography>
          <Box sx={{ minWidth: 108 }}>
            <BandChip passRate={item.pass_rate} />
          </Box>
        </Box>
      ))}
    </Stack>
  );
}

export default function BreakdownsDrawer({ testRunId }: BreakdownsDrawerProps) {
  const [expanded, setExpanded] = useState(false);
  const [insights, setInsights] = useState<InsightsQueryResponse | null>(null);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummary | null>(
    null
  );
  const [isLoading, setIsLoading] = useState(false);
  const isMounted = useRef(true);
  const fetched = useRef(false);

  const fetchBreakdowns = useCallback(async () => {
    if (fetched.current) return;
    fetched.current = true;
    setIsLoading(true);
    try {
      const client = new ApiClientFactory().getInsightsClient();
      const filters = { test_run_ids: [testRunId] };
      const measures = ['passed', 'failed', 'pass_rate'];
      const [insightsResult, testResults] = await Promise.all([
        client.getInsightsQuery({
          categories: {
            entity: 'test_result',
            group_by: ['category'],
            measures,
            filters,
          },
          topics: {
            entity: 'test_result',
            group_by: ['topic'],
            measures,
            filters,
          },
        }),
        fetchAllTestResults(testRunId),
      ]);
      if (isMounted.current) {
        setInsights(insightsResult);
        setReviewSummary(computeReviewSummary(testResults));
        setIsLoading(false);
      }
    } catch {
      if (isMounted.current) setIsLoading(false);
    }
  }, [testRunId]);

  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  const handleExpand = useCallback(
    (_e: React.SyntheticEvent, exp: boolean) => {
      setExpanded(exp);
      if (exp) void fetchBreakdowns();
    },
    [fetchBreakdowns]
  );

  const categories = useMemo(
    () => namedDimensionItems(insights?.categories?.rows ?? [], 'category'),
    [insights]
  );
  const topics = useMemo(
    () => namedDimensionItems(insights?.topics?.rows ?? [], 'topic'),
    [insights]
  );

  // Reviews always has content once fetched (even "0 reviews"), matching
  // the always-visible old Reviews KPI card.
  const hasData = categories.length > 0 || topics.length > 0 || !!reviewSummary;
  if (!isLoading && !expanded && !hasData && fetched.current) return null;

  return (
    <Accordion
      expanded={expanded}
      onChange={handleExpand}
      variant="outlined"
      sx={{
        borderRadius: theme => `${theme.shape.borderRadius}px !important`,
        '&:before': { display: 'none' },
      }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Typography variant="subtitle1" fontWeight={600}>
          Breakdowns
        </Typography>
      </AccordionSummary>
      <AccordionDetails sx={{ pt: 0 }}>
        {isLoading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
            <CircularProgress size={24} />
          </Box>
        ) : !hasData ? (
          <Typography color="text.secondary" variant="body2">
            No breakdown data available.
          </Typography>
        ) : (
          <Grid container spacing={4}>
            {reviewSummary && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography
                  variant="subtitle2"
                  fontWeight={600}
                  sx={{ mb: 1.5 }}
                >
                  Reviews
                </Typography>
                <ReviewsSummary summary={reviewSummary} />
              </Grid>
            )}
            {categories.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography
                  variant="subtitle2"
                  fontWeight={600}
                  sx={{ mb: 1.5 }}
                >
                  Categories
                </Typography>
                <DimensionList items={categories} />
              </Grid>
            )}
            {topics.length > 0 && (
              <Grid size={{ xs: 12, md: 6 }}>
                <Typography
                  variant="subtitle2"
                  fontWeight={600}
                  sx={{ mb: 1.5 }}
                >
                  Topics
                </Typography>
                <DimensionList items={topics} />
              </Grid>
            )}
          </Grid>
        )}
      </AccordionDetails>
    </Accordion>
  );
}
