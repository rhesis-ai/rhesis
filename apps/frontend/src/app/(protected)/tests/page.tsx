'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import { useSession } from 'next-auth/react';
import TestsGrid from './components/TestsGrid';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { useOnboarding } from '@/contexts/OnboardingContext';
import { ApiClientFactory } from '@/utils/api-client/client-factory';
import TestTypeSelectionScreen from './new-generated/components/TestTypeSelectionScreen';
import SelectTestCreationMethod from './new-generated/components/SelectTestCreationMethod';
import {
  TestType,
  TestTemplate,
} from './new-generated/components/shared/types';
import PageHeader from '@/components/layout/PageHeader';
import DataCard from '@/components/common/DataCard';
import FloatingActionButton from '@/components/common/FloatingActionButton';
import AddIcon from '@mui/icons-material/AddOutlined';
import DownloadIcon from '@mui/icons-material/FileDownloadOutlined';

export default function TestsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [_testCount, setTestCount] = React.useState(0);
  const [showTestTypeModal, setShowTestTypeModal] = React.useState(false);
  const [selectedTestType, setSelectedTestType] =
    React.useState<TestType | null>(null);
  const {
    markStepComplete: _markStepComplete,
    progress: _progress,
    activeTour,
    startTour,
    isComplete: _isComplete,
  } = useOnboarding();

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
    if (openGeneration === 'true' && !showTestTypeModal) {
      setShowTestTypeModal(true);
      const newUrl = new URL(window.location.href);
      newUrl.searchParams.delete('openGeneration');
      window.history.replaceState({}, '', newUrl.toString());
    }
  }, [searchParams, showTestTypeModal]);

  React.useEffect(() => {
    const fetchTestCount = async () => {
      if (!session?.session_token) return;

      try {
        const apiFactory = new ApiClientFactory(session.session_token);
        const testsClient = apiFactory.getTestsClient();
        const response = await testsClient.getTests({ skip: 0, limit: 1 });
        setTestCount(response.pagination?.totalCount || 0);
      } catch (_error) {
        // Silently fail
      }
    };

    fetchTestCount();
  }, [session?.session_token, refreshKey]);

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleOpenModal = React.useCallback(() => {
    if (activeTour === 'testCases') {
      return;
    }
    setShowTestTypeModal(true);
  }, [activeTour]);

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
    setSelectedTestType(testType);
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('testType', testType);
    }
  }, []);

  const handleBackToTestType = React.useCallback(() => {
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
    setShowTestTypeModal(false);
    router.push('/tests/new-generated');
  }, [router]);

  const handleSelectManual = React.useCallback(() => {
    setShowTestTypeModal(false);
    router.push('/tests/new-manual');
  }, [router]);

  const handleSelectTemplate = React.useCallback(
    (template: TestTemplate) => {
      if (typeof window !== 'undefined') {
        sessionStorage.setItem('selectedTemplateId', template.id);
      }
      setShowTestTypeModal(false);
      router.push('/tests/new-generated');
    },
    [router]
  );

  if (status === 'loading') {
    return (
      <Box sx={{ p: 4 }}>
        <Typography>Loading...</Typography>
      </Box>
    );
  }

  if (!session?.session_token) {
    return (
      <Box sx={{ p: 4 }}>
        <Typography color="error">No session token available</Typography>
      </Box>
    );
  }

  return (
    <>
      <PageHeader
        title="Tests"
        description="Manage and organize your test cases"
        breadcrumbs={[
          { label: 'Home', href: '/dashboard' },
          { label: 'Tests' },
        ]}
        actions={
          <>
            <FloatingActionButton
              icon={<DownloadIcon />}
              tooltip="Export tests"
            />
            <FloatingActionButton
              icon={<AddIcon />}
              tooltip="Add tests"
              onClick={handleOpenModal}
              disabled={shouldDisableAddButton}
            />
          </>
        }
      />

      <Box sx={{ px: 4, pb: 4, pt: 5 }}>
        <DataCard>
          <TestsGrid
            sessionToken={session.session_token}
            onRefresh={handleRefresh}
            onNewTest={handleOpenModal}
            disableAddButton={shouldDisableAddButton}
          />
        </DataCard>
      </Box>

      {!selectedTestType && (
        <TestTypeSelectionScreen
          open={showTestTypeModal}
          onClose={handleCloseTestTypeModal}
          onSelectTestType={handleTestTypeSelection}
        />
      )}

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
