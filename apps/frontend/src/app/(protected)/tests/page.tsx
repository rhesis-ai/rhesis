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
import { useOnboarding } from '@/contexts/OnboardingContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestTypeSelectionScreen from './new-generated/components/TestTypeSelectionScreen';
import SelectTestCreationMethod from './new-generated/components/SelectTestCreationMethod';
import {
  TestType,
  TestTemplate,
} from './new-generated/components/shared/types';

export default function TestsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [testCount, setTestCount] = React.useState(0);
  const [showTestTypeModal, setShowTestTypeModal] = React.useState(false);
  const [selectedTestType, setSelectedTestType] =
    React.useState<TestType | null>(null);
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

  // Disable "Add Tests" button ONLY when user is actively on a tour OTHER than testCases
  const shouldDisableAddButton = activeTour !== null && !isOnTestCasesTour;

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

  // Check for openGeneration query parameter
  React.useEffect(() => {
    const openGeneration = searchParams?.get('openGeneration');
    if (openGeneration === 'true' && !showTestTypeModal) {
      setShowTestTypeModal(true);
      // Remove the query parameter from URL
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.delete('openGeneration');
      window.history.replaceState({}, '', newUrl.toString());
    }
  }, [searchParams, showTestTypeModal]);

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
    // Open test type selection modal
    setShowTestTypeModal(true);
  }, [activeTour]);

  // Listen for tour event to open modal (needed because programmatic clicks on disabled buttons don't work)
  React.useEffect(() => {
    const handleTourOpenModal = () => {
      setShowTestTypeModal(true);
    };
    window.addEventListener('tour-open-test-modal', handleTourOpenModal);
    return () => {
      window.removeEventListener('tour-open-test-modal', handleTourOpenModal);
    };
  }, []);

  const handleTestTypeSelection = React.useCallback((testType: TestType) => {
    // Store test type and move to step 2 (method selection)
    setSelectedTestType(testType);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('testType', testType);
    }
    // Keep modal open, just move to step 2
  }, []);

  const handleBackToTestType = React.useCallback(() => {
    // Go back to test type selection (step 1)
    setSelectedTestType(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('testType');
    }
  }, []);

  const handleCloseTestTypeModal = React.useCallback(() => {
    setShowTestTypeModal(false);
    setSelectedTestType(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('testType');
    }
  }, []);

  const handleSelectAI = React.useCallback(() => {
    // Close modal and navigate to AI generation flow
    setShowTestTypeModal(false);
    router.push('/tests/new-generated');
  }, [router]);

  const handleSelectManual = React.useCallback(() => {
    // Close modal and navigate to manual test creation
    setShowTestTypeModal(false);
    router.push('/tests/new-manual');
  }, [router]);

  const handleSelectTemplate = React.useCallback(
    (template: TestTemplate) => {
      // Store template ID, close modal, and navigate to generation flow
      if (typeof window !== 'undefined') {
        sessionStorage.setItem('selectedTemplateId', template.id);
      }
      setShowTestTypeModal(false);
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

      {/* Test Creation Modals - Step 1: Test Type Selection */}
      {!selectedTestType && (
        <TestTypeSelectionScreen
          open={showTestTypeModal}
          onClose={handleCloseTestTypeModal}
          onSelectTestType={handleTestTypeSelection}
        />
      )}

      {/* Step 2: Creation Method Selection */}
      {selectedTestType && (
        <SelectTestCreationMethod
          open={showTestTypeModal}
          onClose={handleCloseTestTypeModal}
          onBack={handleBackToTestType}
          onSelectAI={handleSelectAI}
          onSelectManual={handleSelectManual}
          onSelectTemplate={handleSelectTemplate}
          testType={selectedTestType}
        />
      )}
    </>
  );
}
