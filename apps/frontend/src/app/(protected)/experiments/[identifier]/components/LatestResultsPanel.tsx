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
import Link from 'next/link';
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

export default function LatestResultsPanel({
  experimentId,
  sessionToken,
}: LatestResultsPanelProps) {
  const [tab, setTab] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ExperimentResultsRunItem[]>([]);
  const [versions, setVersions] = useState<ExperimentResultsVersionItem[]>([]);

  const apiFactory = useMemo(() => new ApiClientFactory(sessionToken), [sessionToken]);

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

  return (
    <Paper variant="outlined" sx={{ mt: 4 }}>
      <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
        <Tabs value={tab} onChange={(_, v) => setTab(v)}>
          <Tab label="Latest runs (by run)" />
          <Tab label="Config diff (by version)" />
        </Tabs>
      </Box>

      <Box sx={{ p: 2 }}>
        {loading ? (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <CircularProgress size={20} />
            <Typography color="text.secondary">Loading results...</Typography>
          </Box>
        ) : error ? (
          <Alert severity="error">{error}</Alert>
        ) : tab === 0 ? (
          <RunsView runs={runs} />
        ) : (
          <VersionsView versions={versions} />
        )}
      </Box>
    </Paper>
  );
}

function RunsView({ runs }: { runs: ExperimentResultsRunItem[] }) {
  if (runs.length === 0) {
    return <Typography color="text.secondary">No test runs found for this experiment.</Typography>;
  }

  return (
    <TableContainer>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Run</TableCell>
            <TableCell>Created</TableCell>
            <TableCell>Version</TableCell>
            <TableCell>Source</TableCell>
            <TableCell>Tests</TableCell>
            <TableCell>Passed</TableCell>
            <TableCell>Failed</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {runs.map(run => {
            const attr = run.attributes || {};
            const total = attr.total_tests || 0;
            const passed = attr.passed_tests || 0;
            const failed = attr.failed_tests || 0;
            const version = attr.parameter_version;
            const sourceLabel = attr.parameter_source_label;
            
            return (
              <TableRow key={run.id}>
                <TableCell>
                  <Link href={`/test-runs/${run.id}`} style={{ textDecoration: 'none' }}>
                    <Typography color="primary" variant="body2">
                      {run.name || run.id.substring(0, 8)}
                    </Typography>
                  </Link>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {run.created_at ? new Date(run.created_at).toLocaleString() : ''}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2">{shortVersion(version)}</Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {sourceLabel ? `via ${sourceLabel}` : ''}
                  </Typography>
                </TableCell>
                <TableCell>{total}</TableCell>
                <TableCell sx={{ color: passed > 0 ? 'success.main' : 'inherit' }}>{passed}</TableCell>
                <TableCell sx={{ color: failed > 0 ? 'error.main' : 'inherit' }}>{failed}</TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </TableContainer>
  );
}

function VersionsView({ versions }: { versions: ExperimentResultsVersionItem[] }) {
  if (versions.length === 0) {
    return <Typography color="text.secondary">No version history with test runs found.</Typography>;
  }

  // Pre-calculate pass rates so we can show deltas
  const stats = versions.map(v => {
    let passed = 0;
    let failed = 0;
    v.runs.forEach(r => {
      passed += (r.attributes?.passed_tests || 0);
      failed += (r.attributes?.failed_tests || 0);
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
        if (currentStat.passRate !== null && prevStat?.passRate !== null) {
          const delta = currentStat.passRate - prevStat.passRate;
          if (delta > 0) deltaStr = ` (+${delta}pp)`;
          else if (delta < 0) {
            deltaStr = ` (${delta}pp)`;
            isRegression = delta <= -5; // Highlight if regression is 5pp or worse
          } else deltaStr = ` (0pp)`;
        }
        
        const hasDiff = v.diff && Object.keys(v.diff).length > 0;

        return (
          <Card key={v.version} variant="outlined" sx={{ borderColor: isRegression ? 'error.main' : 'divider' }}>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 2 }}>
                <Stack direction="row" spacing={2} alignItems="center">
                  <Typography variant="subtitle1" fontWeight="bold">
                    {shortVersion(v.version)}
                  </Typography>
                  {isRegression && (
                    <Typography variant="caption" color="error.main" fontWeight="bold">
                      Regression Alert
                    </Typography>
                  )}
                </Stack>
                <Typography variant="body2" color={isRegression ? 'error.main' : 'text.secondary'} fontWeight={isRegression ? 'bold' : 'normal'}>
                  {v.runs.length} run{v.runs.length === 1 ? '' : 's'} • Pass rate: {currentStat.total > 0 ? `${currentStat.passRate}%` : 'N/A'}
                  {deltaStr}
                </Typography>
              </Box>

              {hasDiff ? (
                <TableContainer component={Paper} variant="outlined" sx={{ mb: 2 }}>
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
                          <TableCell sx={{ fontWeight: 'medium' }}>{key}</TableCell>
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
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
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
