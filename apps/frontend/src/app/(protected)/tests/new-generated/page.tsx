'use client';

import { useState, useEffect } from 'react';
import { useSession } from 'next-auth/react';
import TestTypeSelectionScreen from './components/TestTypeSelectionScreen';
import TestGenerationFlow from './components/TestGenerationFlow';
import LandingScreen from './components/LandingScreen';
import { TestType } from './components/shared/types';
import { Box, CircularProgress, Typography } from '@mui/material';
import { useRouter } from 'next/navigation';

export default function GenerateTestsPage() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const [testType, setTestType] = useState<TestType | null>(null);
  const [showLandingScreen, setShowLandingScreen] = useState(false);
  const [flowStarted, setFlowStarted] = useState(false);

  // Check for existing test type or template in sessionStorage on mount
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const storedTestType = sessionStorage.getItem(
        'testType'
      ) as TestType | null;
      const hasTemplate = sessionStorage.getItem('selectedTemplateId') !== null;

      if (storedTestType) {
        setTestType(storedTestType);
        // If there's a template, start the flow immediately
        if (hasTemplate) {
          setFlowStarted(true);
        }
      }
    }
  }, []);

  const handleTestTypeSelection = (selectedTestType: TestType) => {
    setTestType(selectedTestType);
    // Store in sessionStorage
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('testType', selectedTestType);
    }
    // Show landing screen after test type is selected
    setShowLandingScreen(true);
  };

  const handleCloseLanding = () => {
    // User closed the modal, go back to test type selection
    setShowLandingScreen(false);
    setTestType(null);
    if (typeof window !== 'undefined') {
      sessionStorage.removeItem('testType');
    }
  };

  const handleSelectAI = () => {
    // Close landing screen and start the flow
    setShowLandingScreen(false);
    setFlowStarted(true);
  };

  const handleSelectManual = () => {
    // Navigate to manual test creation
    router.push('/tests/new');
  };

  const handleSelectTemplate = (template: any) => {
    // Store template ID, close landing screen, and start flow
    if (typeof window !== 'undefined') {
      sessionStorage.setItem('selectedTemplateId', template.id);
    }
    setShowLandingScreen(false);
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
      {/* Test Type Selection Modal */}
      <TestTypeSelectionScreen
        open={!testType}
        onClose={handleCloseLanding}
        onSelectTestType={handleTestTypeSelection}
      />

      {/* Method Selection Modal (AI/Manual/Template) */}
      {testType && !flowStarted && (
        <LandingScreen
          open={true}
          onClose={handleCloseLanding}
          onSelectAI={handleSelectAI}
          onSelectManual={handleSelectManual}
          onSelectTemplate={handleSelectTemplate}
          testType={testType}
        />
      )}

      {/* Test Generation Flow */}
      {flowStarted && (
        <TestGenerationFlow sessionToken={session.session_token} />
      )}
    </div>
  );
}
