'use client';

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { format } from 'date-fns';
import {
  Box,
  Button,
  Chip,
  Link as MuiLink,
  Stack,
  Typography,
} from '@mui/material';
import { alpha, useTheme } from '@mui/material/styles';
import {
  DataGrid,
  type GridColDef,
  type GridRenderCellParams,
} from '@mui/x-data-grid';
import RateReviewOutlinedIcon from '@mui/icons-material/RateReviewOutlined';
import { SectionCard } from '@/components/common/SectionCard';
import GridBadge from '@/components/common/GridBadge';
import { MentionText } from '@/components/common/MentionTextInput';
import { useNotifications } from '@/components/common/NotificationContext';
import { annotationEntityUrl } from '@/components/annotations/annotation-links';
import { useCan } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ANNOTATION_ENTITY_LABELS,
  type Annotation,
} from '@/utils/api-client/interfaces/annotation';
import type {
  RequirementExample,
  RequirementWithMetrics,
} from '@/utils/api-client/interfaces/requirement';
import { isPassedStatusName } from '@/utils/test-result-status';
import { isTunableMetric } from '@/utils/metric-tunable';
import { useIsAuthenticated } from '@/hooks/useIsAuthenticated';
import type { UUID } from 'crypto';

export const EXAMPLES_EMPTY_TEXT =
  'An annotation becomes an example when you pick this requirement in the annotation drawer. That works on test results and traces, including Playground conversations.';

interface RequirementExamplesProps {
  requirement: RequirementWithMetrics;
  /** Server or test data; skips the first fetch. */
  initialExamples?: RequirementExample[];
}

function annotatorName(annotation: Annotation): string {
  const user = annotation.user;
  return (
    user?.name ||
    [user?.given_name, user?.family_name].filter(Boolean).join(' ') ||
    '—'
  );
}

function sourceLabel(annotation: Annotation): string {
  const label =
    ANNOTATION_ENTITY_LABELS[annotation.entity_type] ?? annotation.entity_type;
  const runName = annotation.context?.test_run_name;
  return runName ? `${label} · ${runName}` : label;
}

/** Annotations linked to this requirement: what good and bad look like. */
export default function RequirementExamples({
  requirement,
  initialExamples,
}: RequirementExamplesProps) {
  const theme = useTheme();
  const notifications = useNotifications();
  const isAuthenticated = useIsAuthenticated();
  const canAddCase = useCan(Capability.Metric.UPDATE);
  const [examples, setExamples] = useState<RequirementExample[] | null>(
    initialExamples ?? null
  );
  const [busyId, setBusyId] = useState<string | null>(null);

  const tunableMetrics = useMemo(
    () => (requirement.metrics ?? []).filter(m => isTunableMetric(m)),
    [requirement.metrics]
  );
  const metricNames = useMemo(
    () => new Map((requirement.metrics ?? []).map(m => [String(m.id), m.name])),
    [requirement.metrics]
  );

  const load = useCallback(async () => {
    try {
      const rows = await new ApiClientFactory()
        .getRequirementClient()
        .getExamples(requirement.id as UUID);
      setExamples(rows);
    } catch {
      setExamples([]);
      notifications.show('Failed to load examples', { severity: 'error' });
    }
  }, [requirement.id, notifications]);

  useEffect(() => {
    if (initialExamples || !isAuthenticated) return;
    void load();
  }, [initialExamples, isAuthenticated, load]);

  const addAsTuningCase = useCallback(
    async (example: RequirementExample) => {
      const annotationId = String(example.annotation.id);
      const existing = new Set(
        example.tuning_cases.map(c => String(c.metric_id))
      );
      const targets = tunableMetrics.filter(m => !existing.has(String(m.id)));
      if (targets.length === 0) return;
      setBusyId(annotationId);
      const client = new ApiClientFactory().getAnnotationsClient();
      const results = await Promise.allSettled(
        targets.map(m => client.addAsTuningCase(annotationId, String(m.id)))
      );
      const added = results.flatMap(r =>
        r.status === 'fulfilled' ? [r.value] : []
      );
      setExamples(prev =>
        (prev ?? []).map(e =>
          String(e.annotation.id) === annotationId
            ? { ...e, tuning_cases: [...e.tuning_cases, ...added] }
            : e
        )
      );
      if (added.length < targets.length) {
        notifications.show('Some tuning cases could not be added', {
          severity: 'warning',
        });
      }
      setBusyId(null);
    },
    [tunableMetrics, notifications]
  );

  const columns = useMemo<GridColDef<RequirementExample>[]>(
    () => [
      {
        field: 'conversation',
        headerName: 'Conversation',
        flex: 2,
        minWidth: 240,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<RequirementExample>) => (
          <Stack sx={{ minWidth: 0 }}>
            <Typography
              variant="body2"
              fontWeight="bold"
              noWrap
              title={row.input ?? ''}
            >
              {row.input || '—'}
            </Typography>
            <Typography
              variant="body2"
              color="text.secondary"
              noWrap
              title={row.output ?? ''}
            >
              {row.output || '—'}
            </Typography>
          </Stack>
        ),
      },
      {
        field: 'verdict',
        headerName: 'Verdict',
        width: 110,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<RequirementExample>) => {
          const name = row.annotation.status?.name;
          if (!name) return '—';
          const passed = isPassedStatusName(name);
          return (
            <GridBadge
              label={passed ? 'Pass' : 'Fail'}
              sx={{
                bgcolor: alpha(
                  passed
                    ? theme.palette.success.main
                    : theme.palette.error.main,
                  0.12
                ),
                color: passed ? 'success.dark' : 'error.dark',
              }}
            />
          );
        },
      },
      {
        field: 'comment',
        headerName: 'Comment',
        flex: 1.5,
        minWidth: 180,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<RequirementExample>) => (
          <Typography
            variant="body2"
            noWrap
            title={row.annotation.comments ?? ''}
            sx={{ color: 'text.secondary' }}
          >
            {row.annotation.comments ? (
              <MentionText text={row.annotation.comments} />
            ) : (
              '—'
            )}
          </Typography>
        ),
      },
      {
        field: 'from',
        headerName: 'From',
        flex: 1.2,
        minWidth: 170,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<RequirementExample>) => {
          const url = annotationEntityUrl(row.annotation);
          const label = sourceLabel(row.annotation);
          return (
            <Stack sx={{ minWidth: 0 }}>
              {url ? (
                <MuiLink
                  href={url}
                  target="_blank"
                  rel="noopener noreferrer"
                  variant="body2"
                  underline="hover"
                  noWrap
                >
                  {label}
                </MuiLink>
              ) : (
                <Typography variant="body2" noWrap>
                  {label}
                </Typography>
              )}
              <Typography variant="caption" color="text.secondary" noWrap>
                {annotatorName(row.annotation)} ·{' '}
                {format(new Date(row.annotation.created_at), 'dd/MM/yyyy')}
              </Typography>
            </Stack>
          );
        },
      },
      {
        field: 'tuning',
        headerName: 'Tuning',
        flex: 1.2,
        minWidth: 180,
        sortable: false,
        renderCell: ({ row }: GridRenderCellParams<RequirementExample>) => {
          const caseMetricIds = new Set(
            row.tuning_cases.map(c => String(c.metric_id))
          );
          const missing = tunableMetrics.some(
            m => !caseMetricIds.has(String(m.id))
          );
          return (
            <Stack
              direction="row"
              spacing={0.5}
              useFlexGap
              flexWrap="wrap"
              alignItems="center"
            >
              {row.tuning_cases.map(c => (
                <Chip
                  key={`${c.metric_id}-${c.case_id}`}
                  size="small"
                  color="success"
                  variant="outlined"
                  component={Link}
                  href={`/metrics/${c.metric_id}?tab=tuning`}
                  clickable
                  label={metricNames.get(String(c.metric_id)) ?? 'Tuning case'}
                />
              ))}
              {missing && canAddCase && (
                <Button
                  size="small"
                  disabled={busyId !== null}
                  onClick={() => void addAsTuningCase(row)}
                >
                  {busyId === String(row.annotation.id)
                    ? 'Adding…'
                    : 'Add as tuning case'}
                </Button>
              )}
              {row.tuning_cases.length === 0 && !missing && (
                <Typography variant="body2" color="text.secondary">
                  —
                </Typography>
              )}
            </Stack>
          );
        },
      },
    ],
    [theme, tunableMetrics, metricNames, canAddCase, busyId, addAsTuningCase]
  );

  return (
    <SectionCard
      title="Examples"
      subtitle="Annotations linked to this requirement"
    >
      {examples !== null && examples.length === 0 ? (
        // Same empty block as the Linked Metrics grid, without a nested card.
        <Box
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            py: 5,
            gap: 2,
            textAlign: 'center',
          }}
        >
          <RateReviewOutlinedIcon
            sx={{ fontSize: 32, color: 'primary.main' }}
          />
          <Typography
            variant="h6"
            sx={{ fontWeight: 600, color: 'primary.main' }}
          >
            No examples yet
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {EXAMPLES_EMPTY_TEXT}
          </Typography>
        </Box>
      ) : (
        <Box sx={{ width: '100%' }}>
          <DataGrid
            rows={examples ?? []}
            columns={columns}
            loading={examples === null}
            getRowId={row => String(row.annotation.id)}
            getRowHeight={() => 'auto'}
            disableRowSelectionOnClick
            disableColumnMenu
            pageSizeOptions={[10, 25, 50]}
            initialState={{ pagination: { paginationModel: { pageSize: 10 } } }}
            autoHeight
            // Auto-height rows top-align cells by default; centre them all.
            sx={{
              '& .MuiDataGrid-cell': {
                display: 'flex',
                alignItems: 'center',
                py: 1,
              },
            }}
          />
        </Box>
      )}
    </SectionCard>
  );
}
