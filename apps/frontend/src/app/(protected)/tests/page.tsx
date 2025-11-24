'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import { useSession } from 'next-auth/react';
import { PageContainer } from '@toolpad/core/PageContainer';
import TestsGrid from './components/TestsGrid';
import TestCharts from './components/TestCharts';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import LandingScreen from './new-generated/components/LandingScreen';
import { TestTemplate } from './new-generated/components/shared/types';
import { useOnboardingTour } from '@/hooks/useOnboardingTour';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

export default function TestsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [showModal, setShowModal] = React.useState(false);
  const [testCount, setTestCount] = React.useState(0);
  const [chartsLoaded, setChartsLoaded] = React.useState(false);
  const { markStepComplete, progress, activeTour, startTour, isComplete } =
    useOnboarding();

  // Set document title
  useDocumentTitle('Tests');

  // Don't use the auto-tour hook, we'll manually control it after charts load
  const tourParam = searchParams?.get('tour');

  // Check if user is currently on the testCases tour
  const isOnTestCasesTour =
    tourParam === 'testCases' || activeTour === 'testCases';

  // Disable "Add Tests" button when onboarding is active, UNLESS user is on the testCases tour
  const shouldDisableAddButton =
    !progress.dismissed && !isComplete && !isOnTestCasesTour;

  // Start tour only after charts are loaded
  React.useEffect(() => {
    if (tourParam === 'testCases' && chartsLoaded) {
      // Small additional delay to ensure button is positioned correctly
      const timeout = setTimeout(() => {
        startTour('testCases');
      }, 300);
      return () => clearTimeout(timeout);
    }
  }, [tourParam, chartsLoaded, startTour]);

  // No auto-close logic needed - tour handles modal closing

  // Fetch test count to check if user has created tests
  React.useEffect(() => {
    const fetchTestCount = async () => {
      if (!session?.session_token) return;

      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const testsClient = apiFactory.getTestsClient();
        const response = await testsClient.getTests({ skip: 0, limit: 1 });
        setTestCount(response.pagination?.totalCount || 0);
      } catch (error) {
        // Silently fail
      }
    };

    fetchTestCount();
  }, [session?.session_token, refreshKey]);

  // Tour completion is handled in OnboardingContext when "Got it!" is clicked
  // We don't auto-complete based on test count to avoid marking it done prematurely

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleChartsLoaded = React.useCallback(() => {
    setChartsLoaded(true);
  }, []);

  const handleOpenModal = React.useCallback(() => {
    // Prevent manual clicks when tour is active - tour handles modal opening
    if (activeTour === 'testCases') {
      return;
    }
    setShowModal(true);
  }, [activeTour]);

  // Listen for tour event to open modal (needed because programmatic clicks on disabled buttons don't work)
  React.useEffect(() => {
    const handleTourOpenModal = () => {
      setShowModal(true);
    };
    window.addEventListener('tour-open-test-modal', handleTourOpenModal);
    return () => {
      window.removeEventListener('tour-open-test-modal', handleTourOpenModal);
    };
  }, []);

  const handleCloseModal = React.useCallback(() => {
    setShowModal(false);
  }, []);

  const handleSelectAI = React.useCallback(() => {
    // Close modal before navigation
    setShowModal(false);
    router.push('/tests/new-generated');
  }, [router]);

  const handleSelectManual = React.useCallback(() => {
    // Close modal before navigation
    setShowModal(false);
    router.push('/tests/new-manual');
  }, [router]);

  const handleSelectTemplate = React.useCallback(
    (template: TestTemplate) => {
      // Store only template ID (icon component can't be serialized)
      sessionStorage.setItem('selectedTemplateId', template.id);
      // Close modal before navigation
      setShowModal(false);
      router.push('/tests/new-generated');
    },
    [router]
  );

  // Handle loading state
  if (status === 'loading') {
    return (
      <PageContainer
        title="Tests"
        breadcrumbs={[{ title: 'Tests', path: '/tests' }]}
      >
        <Box sx={{ p: 3 }}>
          <Typography>Loading...</Typography>
        </Box>
      </PageContainer>
    );
  }

  // Handle no session state
  if (!session?.session_token) {
    return (
      <PageContainer
        title="Tests"
        breadcrumbs={[{ title: 'Tests', path: '/tests' }]}
      >
        <Box sx={{ p: 3 }}>
          <Typography color="error">No session token available</Typography>
        </Box>
      </PageContainer>
    );
  }

  return (
    <>
      <PageContainer
        title="Tests"
        breadcrumbs={[{ title: 'Tests', path: '/tests' }]}
      >
        {/* Charts Section */}
        <TestCharts
          sessionToken={session.session_token}
          key={`charts-${refreshKey}`}
          onLoadComplete={handleChartsLoaded}
        />

        {/* Table Section */}
        <Paper sx={{ width: '100%', mb: 2, mt: 2 }}>
          <Box sx={{ p: 2 }}>
            <TestsGrid
              sessionToken={session.session_token}
              onRefresh={handleRefresh}
              onNewTest={handleOpenModal}
              disableAddButton={shouldDisableAddButton}
            />
          </Box>
        </Paper>
      </PageContainer>

      {/* Test Generation Modal */}
      <LandingScreen
        open={showModal}
        onClose={handleCloseModal}
        onSelectAI={handleSelectAI}
        onSelectManual={handleSelectManual}
        onSelectTemplate={handleSelectTemplate}
      />
    </>
  );
}
