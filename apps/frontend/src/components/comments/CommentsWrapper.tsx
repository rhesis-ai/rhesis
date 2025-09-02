'use client';

import React from 'react';
import { Box } from '@mui/material';
import { CommentsSection } from './CommentsSection';
import { useComments } from '@/hooks/useComments';

interface CommentsWrapperProps {
  entityType: 'Test' | 'TestSet' | 'TestRun' | 'TestResult' | 'Metric' | 'Model' | 'Prompt' | 'Behavior' | 'Category';
  entityId: string;
  sessionToken: string;
  currentUserId: string;
}

export default function CommentsWrapper({ entityType, entityId, sessionToken, currentUserId }: CommentsWrapperProps) {
  const {
    comments,
    isLoading,
    error,
    createComment,
    editComment,
    deleteComment,
    reactToComment,
    refetch
  } = useComments({
    entityType,
    entityId,
    sessionToken,
    currentUserId
  });

  // Wrap the functions to match the expected Promise<void> return type
  const handleCreateComment = async (text: string): Promise<void> => {
    await createComment(text);
  };

  const handleEditComment = async (commentId: string, newText: string): Promise<void> => {
    await editComment(commentId, newText);
  };

  const handleDeleteComment = async (commentId: string): Promise<void> => {
    await deleteComment(commentId);
  };

  const handleReactToComment = async (commentId: string, emoji: string): Promise<void> => {
    await reactToComment(commentId, emoji);
  };

  return (
    <Box>
      <CommentsSection
        entityType={entityType}
        entityId={entityId}
        comments={comments}
        onCreateComment={handleCreateComment}
        onEditComment={handleEditComment}
        onDeleteComment={handleDeleteComment}
        onReactToComment={handleReactToComment}
        currentUserId={currentUserId}
        isLoading={isLoading}
      />
    </Box>
  );
}
