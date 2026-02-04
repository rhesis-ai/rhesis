'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { Box, Paper, Typography, Snackbar, Alert, CircularProgress } from '@mui/material';
import TopicTreeView, { AdaptiveTest } from './TopicTreeView';
import AdaptiveTestsGrid from './AdaptiveTestsGrid';
import { ApiClientFactory } from '@/utils/api-client/client-factory';

interface AdaptiveTestsExplorerProps {
  tests: AdaptiveTest[];
  loading: boolean;
  sessionToken?: string;
}

export default function AdaptiveTestsExplorer({
  tests: initialTests,
  loading,
  sessionToken,
}: AdaptiveTestsExplorerProps) {
  const [tests, setTests] = useState<AdaptiveTest[]>(initialTests);
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);
  const [isUpdating, setIsUpdating] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: 'success' | 'error';
  }>({ open: false, message: '', severity: 'success' });

  // Handle moving a test to a new topic
  const handleTestDrop = useCallback(
    async (testId: string, newTopicPath: string) => {
      if (!sessionToken) {
        setSnackbar({
          open: true,
          message: 'Session token not available',
          severity: 'error',
        });
        return;
      }

      // Find the test being moved
      const test = tests.find(t => t.id === testId);
      if (!test) {
        setSnackbar({
          open: true,
          message: 'Test not found',
          severity: 'error',
        });
        return;
      }

      // Don't do anything if dropping on the same topic
      if (test.topic === newTopicPath) {
        return;
      }

      setIsUpdating(true);

      try {
        const clientFactory = new ApiClientFactory(sessionToken);
        const topicClient = clientFactory.getTopicClient();
        const testsClient = clientFactory.getTestsClient();

        // First, get or create the topic by name
        const topic = await topicClient.getOrCreateTopic(newTopicPath, 'Test');

        // Then update the test with the new topic_id
        await testsClient.updateTest(testId, {
          topic_id: topic.id,
        });

        // Update local state
        setTests(prevTests =>
          prevTests.map(t => (t.id === testId ? { ...t, topic: newTopicPath } : t))
        );

        setSnackbar({
          open: true,
          message: `Test moved to "${decodeURIComponent(newTopicPath)}"`,
          severity: 'success',
        });
      } catch (error) {
        console.error('Failed to update test topic:', error);
        setSnackbar({
          open: true,
          message: `Failed to move test: ${error instanceof Error ? error.message : 'Unknown error'}`,
          severity: 'error',
        });
      } finally {
        setIsUpdating(false);
      }
    },
    [sessionToken, tests]
  );

  const handleCloseSnackbar = () => {
    setSnackbar(prev => ({ ...prev, open: false }));
  };

  // Filter tests based on selected topic
  const filteredTests = useMemo(() => {
    if (selectedTopic === null) {
      return tests;
    }
    return tests.filter(test => {
      const topic = typeof test.topic === 'string' ? test.topic : '';
      // Match exact topic or any subtopic
      return topic === selectedTopic || topic.startsWith(selectedTopic + '/');
    });
  }, [tests, selectedTopic]);

  // Check if we have any topics at all
  const hasTopics = tests.some(test => {
    const topic = typeof test.topic === 'string' ? test.topic : '';
    return topic.length > 0;
  });

  // If no topics, just show the grid
  if (!hasTopics) {
    return (
      <AdaptiveTestsGrid
        tests={tests}
        loading={loading}
        sessionToken={sessionToken}
      />
    );
  }

  return (
    <>
      <Box sx={{ display: 'flex', gap: 2, height: '100%', minHeight: 400 }}>
        {/* Left Panel - Topic Tree */}
        <Paper
          variant="outlined"
          sx={{
            width: 300,
            minWidth: 250,
            maxWidth: 350,
            overflow: 'auto',
            flexShrink: 0,
            position: 'relative',
          }}
        >
          {isUpdating && (
            <Box
              sx={{
                position: 'absolute',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'rgba(255, 255, 255, 0.7)',
                zIndex: 1,
              }}
            >
              <CircularProgress size={24} />
            </Box>
          )}
          <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="subtitle2" fontWeight={600}>
              Topics
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Drag tests to move between topics
            </Typography>
          </Box>
          <Box sx={{ p: 1 }}>
            <TopicTreeView
              tests={tests}
              selectedTopic={selectedTopic}
              onTopicSelect={setSelectedTopic}
              onTestDrop={handleTestDrop}
            />
          </Box>
        </Paper>

        {/* Right Panel - Tests Grid */}
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Box sx={{ mb: 1, display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="subtitle2" color="text.secondary">
              {selectedTopic ? decodeURIComponent(selectedTopic) : 'All Tests'}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              ({filteredTests.length} {filteredTests.length === 1 ? 'test' : 'tests'})
            </Typography>
          </Box>
          <AdaptiveTestsGrid
            tests={filteredTests}
            loading={loading}
            sessionToken={sessionToken}
            enableDragDrop={true}
          />
        </Box>
      </Box>

      {/* Feedback Snackbar */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={handleCloseSnackbar}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={handleCloseSnackbar}
          severity={snackbar.severity}
          variant="filled"
          sx={{ width: '100%' }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </>
  );
}
