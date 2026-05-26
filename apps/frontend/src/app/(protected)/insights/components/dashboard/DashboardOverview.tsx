'use client';

import * as React from 'react';
import Grid from '@mui/material/Grid';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import CircularProgress from '@mui/material/CircularProgress';
import { TestResultsStatsOptions } from '@/utils/api-client/interfaces/common';
import DashboardKPIs from './DashboardKPIs';
import TestRunPerformance from './TestRunPerformance';
import ActivityTimeline from './ActivityTimeline';

interface DashboardOverviewProps {
  sessionToken: string;
  filters: Partial<TestResultsStatsOptions>;
  searchValue: string;
}

export default function DashboardOverview({
  sessionToken,
  filters,
  searchValue,
}: DashboardOverviewProps) {
  const [loadingStates, setLoadingStates] = React.useState({
    kpis: true,
    testRuns: true,
    activities: true,
  });
  const [hasLoadedOnce, setHasLoadedOnce] = React.useState(false);

  const allLoaded =
    !loadingStates.kpis && !loadingStates.testRuns && !loadingStates.activities;

  React.useEffect(() => {
    if (allLoaded) {
      setHasLoadedOnce(true);
    }
  }, [allLoaded]);

  const handleComponentLoad = React.useCallback(
    (component: 'kpis' | 'testRuns' | 'activities') => {
      setLoadingStates(prev => ({ ...prev, [component]: false }));
    },
    []
  );

  const handleKpisLoad = React.useCallback(
    () => handleComponentLoad('kpis'),
    [handleComponentLoad]
  );
  const handleTestRunsLoad = React.useCallback(
    () => handleComponentLoad('testRuns'),
    [handleComponentLoad]
  );
  const handleActivitiesLoad = React.useCallback(
    () => handleComponentLoad('activities'),
    [handleComponentLoad]
  );

  const showFilterScopeNote = Boolean(filters.test_set_ids?.length);

  return (
    <Box>
      {showFilterScopeNote && (
        <Alert severity="info" sx={{ mb: 2 }}>
          Test set filter applies to pass rate and chart tabs. Test counts and
          recent activity show organization-wide data.
        </Alert>
      )}

      {!hasLoadedOnce && !allLoaded && (
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
            minHeight: '40vh',
          }}
        >
          <CircularProgress size={48} />
        </Box>
      )}

      <Box sx={{ display: !hasLoadedOnce && !allLoaded ? 'none' : 'block' }}>
        <DashboardKPIs
          sessionToken={sessionToken}
          filters={filters}
          onLoadComplete={handleKpisLoad}
        />

        <Grid container spacing={3} sx={{ mt: 0 }}>
          <Grid size={{ xs: 12, md: 6 }}>
            <TestRunPerformance
              sessionToken={sessionToken}
              filters={filters}
              searchValue={searchValue}
              onLoadComplete={handleTestRunsLoad}
              limit={7}
            />
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <ActivityTimeline
              sessionToken={sessionToken}
              onLoadComplete={handleActivitiesLoad}
            />
          </Grid>
        </Grid>
      </Box>
    </Box>
  );
}
