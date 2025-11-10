'use client';

import React from 'react';
import { Box, Typography } from '@mui/material';
import { TestResultDetail } from '@/utils/api-client/interfaces/test-results';
import ConversationHistory from '@/components/common/ConversationHistory';

interface TestDetailConversationTabProps {
  test: TestResultDetail;
  testSetType?: string;
}

export default function TestDetailConversationTab({
  test,
  testSetType,
}: TestDetailConversationTabProps) {
  // Determine if this is a multi-turn test
  const isMultiTurn =
    testSetType?.toLowerCase().includes('multi-turn') || false;

  // Get conversation summary
  const conversationSummary = test.test_output?.conversation_summary;
  const hasConversation =
    isMultiTurn && conversationSummary && conversationSummary.length > 0;

  // If not a multi-turn test, show message
  if (!isMultiTurn) {
    return (
      <Box
        sx={{
          p: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 300,
        }}
      >
        <Typography variant="body1" color="text.secondary">
          Conversation history is only available for multi-turn tests.
        </Typography>
      </Box>
    );
  }

  // If no conversation available
  if (!hasConversation) {
    return (
      <Box
        sx={{
          p: 3,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 300,
        }}
      >
        <Typography variant="body1" color="text.secondary">
          No conversation history available for this test.
        </Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{ p: 3, height: '100%', display: 'flex', flexDirection: 'column' }}
    >
      <ConversationHistory
        conversationSummary={conversationSummary}
        maxHeight="100%"
      />
    </Box>
  );
}
