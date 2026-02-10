'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import TestTypeSelectionScreen from './components/TestTypeSelectionScreen';
import TestGenerationFlow from './components/TestGenerationFlow';
import SelectTestCreationMethod from './components/SelectTestCreationMethod';
import { TestType } from './components/shared/types';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useRouter } from 'next/navigation';

export default function GenerateTestsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [testType, setTestType] = useState<TestType | null>(null);
  const [showModal, setShowModal] = useState(true);
  const [flowStarted, setFlowStarted] = useState(false);

  // Check for existing test type or template in sessionStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedTestType = sessionStorage.getItem(
        'testType'
      ) as TestType | null;
      const _hasTemplate = sessionStorage.getItem('selectedTemplateId') !== null;

      if (storedTestType) {
        setTestType(storedTestType);
        // If testType exists, start the flow immediately (user came from /tests page)
        setShowModal(false);
        setFlowStarted(true);
      }
    }
  }, []);

  const handleTestTypeSelection = (selectedTestType: TestType) => {
    setTestType(selectedTestType);
    // Store in sessionStorage
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('testType', selectedTestType);
    }
    // Keep modal open, just switch to creation method view
  };

  const handleCloseModal = () => {
    // User closed the modal completely
    setShowModal(false);
    setTestType(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('testType');
    }
    router.push('/tests');
  };

  const handleBackToTestType = () => {
    // Go back to test type selection
    setTestType(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('testType');
    }
  };

  const handleSelectAI = () => {
    // Close modal and start the flow
    setShowModal(false);
    setFlowStarted(true);
  };

  const handleSelectManual = () => {
    // Navigate to manual test creation
    router.push('/tests/new');
  };

  const handleSelectTemplate = (template: any) => {
    // Store template ID, close modal, and start flow
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('selectedTemplateId', template.id);
    }
    setShowModal(false);
    setFlowStarted(true);
  };

  // Show loading while session is being fetched
  if (status === 'loading') {
    return (
      <Box
        sx={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
        }}
      >
        <CircularProgress sx={{ mb: 2 }} />
        <Typography variant="body1">Loading...</Typography>
      </Box>
    );
  }

  if (!session?.session_token) {
    throw new Error('No session token available');
  }

  return (
    <div style={{ padding: 0 }}>
      {/* Single Modal - switches content based on testType */}
      {!flowStarted && (
        <>
          {!testType ? (
            <TestTypeSelectionScreen
              open={showModal}
              onClose={handleCloseModal}
              onSelectTestType={handleTestTypeSelection}
            />
          ) : (
            <SelectTestCreationMethod
              open={showModal}
              onClose={handleCloseModal}
              onBack={handleBackToTestType}
              onSelectAI={handleSelectAI}
              onSelectManual={handleSelectManual}
              onSelectTemplate={handleSelectTemplate}
              testType={testType}
            />
          )}
        </>
      )}

      {/* Test Generation Flow */}
      {flowStarted && (
        <TestGenerationFlow sessionToken={session.session_token} />
      )}
    </div>
  );
}
