'use client';

import React, { useEffect, useState, useMemo } from 'react';
import {
  Box,
  Typography,
  Paper,
  Tabs,
  Tab,
  CircularProgress,
  Alert,
} from '@mui/material';
import { GridColDef, GridRenderCellParams } from '@mui/x-data-grid';
import Link from 'next/link';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentResultsRunItem,
  ExperimentResultsVersionItem,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';
import type { VersionOutcomeSummary } from './VersionHistory';

interface LatestResultsPanelProps {
  experimentId: string;
  sessionToken: string;
  renderVersionHistory: (
    outcomes: Record<string, VersionOutcomeSummary>
  ) => React.ReactNode;
}

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel({ children, value, index }: TabPanelProps) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`experiment-results-tabpanel-${index}`}
      aria-labelledby={`experiment-results-tab-${index}`}
    >
      {value === index && <Box sx={{ p: 3 }}>{children}</Box>}
    </div>
  );
}

const RESULTS_TABS = [
  {
    label: 'Versions',
    description:
      'Every saved version is kept here. Compare configurations across versions, promote a version to an environment, or audit who changed what and when.',
  },
  {
    label: 'Runs',
    description:
      'Review the latest test runs for this experiment, including the test set, version, execution status, pass rate, and pass/fail counts.',
  },
] as const;

export default function LatestResultsPanel({
  experimentId,
  sessionToken,
  renderVersionHistory,
}: LatestResultsPanelProps) {
  const [tab, setTab] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ExperimentResultsRunItem[]>([]);
  const [versions, setVersions] = useState<ExperimentResultsVersionItem[]>([]);

  const apiFactory = useMemo(
    () => new ApiClientFactory(sessionToken),
    [sessionToken]
  );

  useEffect(() => {
    let mounted = true;
    async function fetchResults() {
      setLoading(true);
      setError(null);
      try {
        const client = apiFactory.getParametersClient();
        if (tab === 1) {
          const res = await client.getExperimentResultsByRun(experimentId);
          if (mounted) setRuns(res.items);
        } else {
          const res = await client.getExperimentResultsByVersion(experimentId);
          if (mounted) setVersions(res.items);
        }
      } catch (e) {
        if (mounted) {
          setError(e instanceof Error ? e.message : 'Failed to load results');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }
    fetchResults();
    return () => {
      mounted = false;
    };
  }, [apiFactory, experimentId, tab]);

  const versionOutcomes = useMemo(() => {
    const stats = versions.map(v => {
      let passed = 0;
      let total = 0;
      v.runs.forEach(r => {
        passed += r.stats?.passed ?? 0;
        total += r.stats?.total ?? 0;
      });
      const passRate = total > 0 ? (passed / total) * 100 : null;
      return { version: v.version, runCount: v.runs.length, passRate };
    });

    return stats.reduce<Record<string, VersionOutcomeSummary>>(
      (acc, current, idx) => {
        const previous = idx < stats.length - 1 ? stats[idx + 1] : null;
        acc[current.version] = {
          runCount: current.runCount,
          passRate: current.passRate,
          delta:
            current.passRate !== null &&
            previous !== null &&
            previous.passRate !== null
              ? current.passRate - previous.passRate
              : null,
        };
        return acc;
      },
      {}
    );
  }, [versions]);

  const statusContent = loading ? (
    <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
      <CircularProgress size={20} />
      <Typography color="text.secondary">Loading results...</Typography>
    </Box>
  ) : error ? (
    <Alert severity="error">{error}</Alert>
  ) : null;

  return (
    <Paper variant="outlined" sx={{ mt: 3 }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs
          value={tab}
          onChange={(_, v) => setTab(v)}
          aria-label="experiment results sections"
        >
          {RESULTS_TABS.map(t => (
            <Tab key={t.label} label={t.label} />
          ))}
        </Tabs>
      </Box>

      <TabPanel value={tab} index={0}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {RESULTS_TABS[0].description}
        </Typography>
        {renderVersionHistory(versionOutcomes)}
      </TabPanel>
      <TabPanel value={tab} index={1}>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {RESULTS_TABS[1].description}
        </Typography>
        {statusContent ?? <RunsView runs={runs} />}
      </TabPanel>
    </Paper>
  );
}

function RunsView({ runs }: { runs: ExperimentResultsRunItem[] }) {
  const columns: GridColDef<ExperimentResultsRunItem>[] = useMemo(
    () => [
      {
        field: 'name',
        headerName: 'Run',
        flex: 1.2,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              height: '100%',
              width: '100%',
            }}
          >
            <Link
              href={`/test-runs/${params.row.id}`}
              style={{ textDecoration: 'none' }}
            >
              <Typography
                variant="body2"
                color="primary"
                sx={{ '&:hover': { textDecoration: 'underline' } }}
              >
                {params.row.name || params.row.id.substring(0, 8)}
              </Typography>
            </Link>
          </Box>
        ),
      },
      {
        field: 'created_at',
        headerName: 'Created',
        flex: 1.2,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2" color="text.secondary">
              {params.row.created_at
                ? new Date(params.row.created_at).toLocaleString()
                : ''}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'test_set',
        headerName: 'Test Set',
        flex: 1.2,
        sortable: false,
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.test_configuration?.test_set?.name ?? '',
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => {
          const testSet = params.row.test_configuration?.test_set;
          if (!testSet?.name) {
            return (
              <Box
                sx={{ display: 'flex', alignItems: 'center', height: '100%' }}
              >
                <Typography variant="body2" color="text.secondary">
                  —
                </Typography>
              </Box>
            );
          }
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              {testSet.id ? (
                <Link
                  href={`/test-sets/${testSet.id}`}
                  style={{ textDecoration: 'none' }}
                >
                  <Typography
                    variant="body2"
                    color="primary"
                    noWrap
                    title={testSet.name}
                    sx={{ '&:hover': { textDecoration: 'underline' } }}
                  >
                    {testSet.name}
                  </Typography>
                </Link>
              ) : (
                <Typography variant="body2" noWrap title={testSet.name}>
                  {testSet.name}
                </Typography>
              )}
            </Box>
          );
        },
      },
      {
        field: 'version',
        headerName: 'Version',
        flex: 0.8,
        sortable: false,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              {shortVersion(params.row.attributes?.parameter_version)}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'total',
        headerName: 'Tests',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.stats?.total ?? 0,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => (
          <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
            <Typography variant="body2">
              {params.row.stats?.total ?? 0}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'passed',
        headerName: 'Passed',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.stats?.passed ?? 0,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => {
          const passed = params.row.stats?.passed ?? 0;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <Typography
                variant="body2"
                sx={{ color: passed > 0 ? 'success.main' : 'inherit' }}
              >
                {passed}
              </Typography>
            </Box>
          );
        },
      },
      {
        field: 'failed',
        headerName: 'Failed',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        valueGetter: (_, row: ExperimentResultsRunItem) =>
          row.stats?.failed ?? 0,
        renderCell: (
          params: GridRenderCellParams<ExperimentResultsRunItem>
        ) => {
          const failed = params.row.stats?.failed ?? 0;
          return (
            <Box sx={{ display: 'flex', alignItems: 'center', height: '100%' }}>
              <Typography
                variant="body2"
                sx={{ color: failed > 0 ? 'error.main' : 'inherit' }}
              >
                {failed}
              </Typography>
            </Box>
          );
        },
      },
    ],
    []
  );

  if (runs.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No test runs found for this experiment.
      </Typography>
    );
  }

  return (
    <Paper elevation={2} sx={{ p: 2 }}>
      <BaseDataGrid
        rows={runs}
        columns={columns}
        getRowId={row => row.id}
        disableRowSelectionOnClick
        hideFooter
        disablePaperWrapper
      />
    </Paper>
  );
}
