'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
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

export default function TestsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [refreshKey, setRefreshKey] = React.useState(0);
  const [showModal, setShowModal] = React.useState(false);

  // Set document title
  useDocumentTitle('Tests');

  const handleRefresh = React.useCallback(() => {
    setRefreshKey(prev => prev + 1);
  }, []);

  const handleOpenModal = React.useCallback(() => {
    setShowModal(true);
  }, []);

  const handleCloseModal = React.useCallback(() => {
    setShowModal(false);
  }, []);

  const handleSelectAI = React.useCallback(() => {
    // Keep modal open during navigation
    router.push('/tests/new-generated');
  }, [router]);

  const handleSelectManual = React.useCallback(() => {
    // Keep modal open during navigation
    router.push('/tests/new-manual');
  }, [router]);

  const handleSelectTemplate = React.useCallback(
    (template: TestTemplate) => {
      // Store only template ID (icon component can't be serialized)
      sessionStorage.setItem('selectedTemplateId', template.id);
      // Keep modal open during navigation
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
        />

        {/* Table Section */}
        <Paper sx={{ width: '100%', mb: 2, mt: 4 }}>
          <Box sx={{ p: 2 }}>
            <TestsGrid
              sessionToken={session.session_token}
              onRefresh={handleRefresh}
              onNewTest={handleOpenModal}
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
