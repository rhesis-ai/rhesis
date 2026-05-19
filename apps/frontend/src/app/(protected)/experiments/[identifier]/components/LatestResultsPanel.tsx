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
  Stack,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from '@mui/material';
import {
  GridColDef,
  GridRenderCellParams,
} from '@mui/x-data-grid';
import Link from 'next/link';
import BaseDataGrid from '@/components/common/BaseDataGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import {
  ExperimentResultsRunItem,
  ExperimentResultsVersionItem,
  shortVersion,
} from '@/utils/api-client/interfaces/parameters';

interface LatestResultsPanelProps {
  experimentId: string;
  sessionToken: string;
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
  { label: 'Latest runs (by run)' },
  { label: 'Config diff (by version)' },
] as const;

export default function LatestResultsPanel({
  experimentId,
  sessionToken,
}: LatestResultsPanelProps) {
  const [tab, setTab] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
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
        if (tab === 0) {
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
        {statusContent ?? <RunsView runs={runs} />}
      </TabPanel>
      <TabPanel value={tab} index={1}>
        {statusContent ?? <VersionsView versions={versions} />}
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
        renderCell: (params: GridRenderCellParams<ExperimentResultsRunItem>) => (
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
        renderCell: (params: GridRenderCellParams<ExperimentResultsRunItem>) => (
          <Box
            sx={{ display: 'flex', alignItems: 'center', height: '100%' }}
          >
            <Typography variant="body2" color="text.secondary">
              {params.row.created_at
                ? new Date(params.row.created_at).toLocaleString()
                : ''}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'version',
        headerName: 'Version',
        flex: 0.8,
        sortable: false,
        renderCell: (params: GridRenderCellParams<ExperimentResultsRunItem>) => (
          <Box
            sx={{ display: 'flex', alignItems: 'center', height: '100%' }}
          >
            <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
              {shortVersion(params.row.attributes?.parameter_version)}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'source',
        headerName: 'Source',
        flex: 1,
        sortable: false,
        renderCell: (params: GridRenderCellParams<ExperimentResultsRunItem>) => {
          const attr = params.row.attributes ?? {};
          const sourceEnvironment =
            (attr.parameter_source_environment as string | undefined) ??
            (attr.parameter_source_label as string | undefined);
          return (
            <Box
              sx={{ display: 'flex', alignItems: 'center', height: '100%' }}
            >
              <Typography variant="body2" color="text.secondary">
                {sourceEnvironment ? `via ${sourceEnvironment}` : ''}
              </Typography>
            </Box>
          );
        },
      },
      {
        field: 'total_tests',
        headerName: 'Tests',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        renderCell: (params: GridRenderCellParams<ExperimentResultsRunItem>) => (
          <Box
            sx={{ display: 'flex', alignItems: 'center', height: '100%' }}
          >
            <Typography variant="body2">
              {params.row.attributes?.total_tests ?? 0}
            </Typography>
          </Box>
        ),
      },
      {
        field: 'passed_tests',
        headerName: 'Passed',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        renderCell: (params: GridRenderCellParams<ExperimentResultsRunItem>) => {
          const passed = params.row.attributes?.passed_tests ?? 0;
          return (
            <Box
              sx={{ display: 'flex', alignItems: 'center', height: '100%' }}
            >
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
        field: 'failed_tests',
        headerName: 'Failed',
        flex: 0.5,
        type: 'number',
        align: 'left',
        headerAlign: 'left',
        renderCell: (params: GridRenderCellParams<ExperimentResultsRunItem>) => {
          const failed = params.row.attributes?.failed_tests ?? 0;
          return (
            <Box
              sx={{ display: 'flex', alignItems: 'center', height: '100%' }}
            >
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

function VersionsView({ versions }: { versions: ExperimentResultsVersionItem[] }) {
  if (versions.length === 0) {
    return (
      <Typography variant="body2" color="text.secondary">
        No version history with test runs found.
      </Typography>
    );
  }

  // Pre-calculate pass rates so we can show deltas
  const stats = versions.map(v => {
    let passed = 0;
    let failed = 0;
    v.runs.forEach(r => {
      passed += r.attributes?.passed_tests || 0;
      failed += r.attributes?.failed_tests || 0;
    });
    const total = passed + failed;
    const passRate = total > 0 ? Math.round((passed / total) * 100) : null;
    return { version: v.version, total, passRate };
  });

  return (
    <Stack spacing={3}>
      {versions.map((v, idx) => {
        const currentStat = stats[idx];
        const prevStat = idx < stats.length - 1 ? stats[idx + 1] : null;

        let deltaStr = '';
        let isRegression = false;
        if (
          currentStat.passRate !== null &&
          prevStat !== null &&
          prevStat.passRate !== null
        ) {
          const delta = currentStat.passRate - prevStat.passRate;
          if (delta > 0) deltaStr = ` (+${delta}pp)`;
          else if (delta < 0) {
            deltaStr = ` (${delta}pp)`;
            isRegression = delta <= -5;
          } else deltaStr = ` (0pp)`;
        }

        const hasDiff = v.diff && Object.keys(v.diff).length > 0;

        return (
          <Card
            key={v.version}
            variant="outlined"
            sx={{ borderColor: isRegression ? 'error.main' : 'divider' }}
          >
            <CardContent>
              <Box
                sx={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  mb: 2,
                }}
              >
                <Stack direction="row" spacing={2} alignItems="center">
                  <Typography variant="subtitle1" fontWeight="bold">
                    {shortVersion(v.version)}
                  </Typography>
                  {isRegression && (
                    <Typography
                      variant="caption"
                      color="error.main"
                      fontWeight="bold"
                    >
                      Regression Alert
                    </Typography>
                  )}
                </Stack>
                <Typography
                  variant="body2"
                  color={isRegression ? 'error.main' : 'text.secondary'}
                  fontWeight={isRegression ? 'bold' : 'normal'}
                >
                  {v.runs.length} run{v.runs.length === 1 ? '' : 's'} • Pass
                  rate:{' '}
                  {currentStat.total > 0 ? `${currentStat.passRate}%` : 'N/A'}
                  {deltaStr}
                </Typography>
              </Box>

              {hasDiff ? (
                <TableContainer
                  component={Paper}
                  variant="outlined"
                  sx={{ mb: 2 }}
                >
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Parameter</TableCell>
                        <TableCell>Before</TableCell>
                        <TableCell>After</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {Object.entries(v.diff).map(([key, changes]) => (
                        <TableRow key={key}>
                          <TableCell sx={{ fontWeight: 'medium' }}>
                            {key}
                          </TableCell>
                          <TableCell sx={{ color: 'text.secondary' }}>
                            {JSON.stringify(changes.before)}
                          </TableCell>
                          <TableCell>{JSON.stringify(changes.after)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 2 }}
                >
                  No parameter changes from previous version.
                </Typography>
              )}
            </CardContent>
          </Card>
        );
      })}
    </Stack>
  );
}
