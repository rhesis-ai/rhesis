'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { useSession } from 'next-auth/react';
import EditNoteIcon from '@mui/icons-material/EditNote';
import DownloadOutlinedIcon from '@mui/icons-material/DownloadOutlined';
import { PageLayout } from '@/components/layout/PageLayout';
import { Fab, FabGroup } from '@/components/common/Fab';
import EntityEmptyState from '@/components/common/EntityEmptyState';
import { getEntityEmptyStateEnrichment } from '@/constants/entity-empty-state-env';
import { ScienceIcon } from '@/components/icons';
import TestsGrid from './components/TestsGrid';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { BORDER_RADIUS, ELEVATION } from '@/styles/theme';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { parseInsightsFailedTestsSearchParams } from '@/app/(protected)/insights/utils/insights-failed-tests';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import { Can, useCan, useCanWithStatus } from '@/components/common/Can';
import { Capability } from '@/constants/capabilities';
import AccessDenied from '@/components/common/AccessDenied';
import PageLoadingState from '@/components/common/PageLoadingState';

export default function TestsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [testCount, setTestCount] = React.useState<number | null>(null);
  const { activeTour, startTour } = useOnboarding();
  const { allowed: canRead, loading: permsLoading } = useCanWithStatus(
    Capability.Test.READ
  );
  const canCreate = useCan(Capability.Test.CREATE);

  const insightsFailedFilter = React.useMemo(
    () =>
      searchParams ? parseInsightsFailedTestsSearchParams(searchParams) : null,
    [searchParams]
  );
  const [insightsEndpointName, setInsightsEndpointName] = React.useState<
    string | undefined
  >();

  useDocumentTitle('Tests');

  const tourParam = searchParams?.get('tour');
  const isOnTestCasesTour =
    tourParam === 'testCases' || activeTour === 'testCases';
  const shouldDisableAddButton = activeTour !== null && !isOnTestCasesTour;

  React.useEffect(() => {
    if (tourParam === 'testCases') {
      const timeout = setTimeout(() => {
        startTour('testCases');
      }, 300);
      return () => clearTimeout(timeout);
    }
  }, [tourParam, startTour]);

  React.useEffect(() => {
    const openGeneration = searchParams?.get('openGeneration');
    if (openGeneration === 'true') {
      router.push('/test-sets/new-generated');
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.delete('openGeneration');
      window.history.replaceState({}, '', newUrl.toString());
    }
  }, [searchParams, router]);

  React.useEffect(() => {
    if (!insightsFailedFilter || !session?.session_token) {
      setInsightsEndpointName(undefined);
      return;
    }

    let cancelled = false;

    const sessionToken = session.session_token;

    const loadEndpointName = async () => {
      try {
        const client = new ApiClientFactory(sessionToken).getEndpointsClient();
        const endpoint = await client.getEndpoint(
          insightsFailedFilter.endpointId
        );
        if (!cancelled) {
          setInsightsEndpointName(endpoint.name);
        }
      } catch {
        if (!cancelled) {
          setInsightsEndpointName(undefined);
        }
      }
    };

    void loadEndpointName();
    return () => {
      cancelled = true;
    };
  }, [insightsFailedFilter, session?.session_token]);

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleCreateManual = React.useCallback(() => {
    if (activeTour === 'testCases') return;
    router.push('/tests/new-manual');
  }, [activeTour, router]);

  React.useEffect(() => {
    const handleTourOpenModal = () => {
      router.push('/test-sets/new-generated');
    };
    window.addEventListener('tour-open-test-modal', handleTourOpenModal);
    return () => {
      window.removeEventListener('tour-open-test-modal', handleTourOpenModal);
    };
  }, [router]);

  if (status === 'loading') {
    return (
      <PageLayout title="Tests" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageLayout>
    );
  }

  if (permsLoading) return <PageLoadingState />;
  if (!canRead) return <AccessDenied resource="tests" />;

  if (!session?.session_token) {
    return (
      <PageLayout title="Tests" breadcrumbs={[]}>
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageLayout>
    );
  }

  return (
    <PageLayout
      title="Tests"
      description="Individual test cases that evaluate your AI endpoints for quality, safety, and reliability."
      breadcrumbs={[]}
      actions={
        <FabGroup>
          <Fab
            icon={<DownloadOutlinedIcon />}
            tooltip="Import tests"
            onClick={() => {}}
          />
          <Can capability={Capability.Test.CREATE}>
            <Fab
              icon={<EditNoteIcon />}
              tooltip="Manual test"
              aria-label="Manual test"
              onClick={handleCreateManual}
              disabled={shouldDisableAddButton}
            />
          </Can>
        </FabGroup>
      }
    >
      <Box sx={{ mt: 2, mb: 2 }}>
        {testCount === 0 ? (
          <EntityEmptyState
            card
            icon={ScienceIcon}
            title="No test yet"
            description="Create your first test to start evaluating your AI endpoints. Tests let you measure quality, safety, and reliability across single-turn and multi-turn interactions."
            actionLabel={canCreate ? 'Create test' : undefined}
            onAction={canCreate ? handleCreateManual : undefined}
            actionDisabled={shouldDisableAddButton}
            enrichment={getEntityEmptyStateEnrichment('tests')}
          />
        ) : (
          <Paper
            sx={{
              width: '100%',
              borderRadius: BORDER_RADIUS.md,
              boxShadow: ELEVATION.xs,
              border: theme => `1px solid ${theme.palette.greyscale.border}`,
              overflow: 'hidden',
            }}
          >
            <TestsGrid
              sessionToken={session.session_token}
              onRefresh={handleRefresh}
              onNewTest={handleCreateManual}
              disableAddButton={shouldDisableAddButton}
              insightsFailedFilter={insightsFailedFilter}
              insightsEndpointName={insightsEndpointName}
              onTotalCountChange={setTestCount}
            />
          </Paper>
        )}
      </Box>
    </PageLayout>
  );
}
