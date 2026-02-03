'use client';

import React, { useState, useMemo } from 'react';
import { Box, Paper, Typography, Divider } from '@mui/material';
import TopicTreeView, { AdaptiveTest } from './TopicTreeView';
import AdaptiveTestsGrid from './AdaptiveTestsGrid';

interface AdaptiveTestsExplorerProps {
  tests: AdaptiveTest[];
  loading: boolean;
  sessionToken?: string;
}

export default function AdaptiveTestsExplorer({
  tests,
  loading,
  sessionToken,
}: AdaptiveTestsExplorerProps) {
  const [selectedTopic, setSelectedTopic] = useState<string | null>(null);

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
        }}
      >
        <Box sx={{ p: 1.5, borderBottom: 1, borderColor: 'divider' }}>
          <Typography variant="subtitle2" fontWeight={600}>
            Topics
          </Typography>
        </Box>
        <Box sx={{ p: 1 }}>
          <TopicTreeView
            tests={tests}
            selectedTopic={selectedTopic}
            onTopicSelect={setSelectedTopic}
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
        />
      </Box>
    </Box>
  );
}
