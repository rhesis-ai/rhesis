'use client';

import React from 'react';
import { Box } from '@mui/material';
import { CommentsSection } from './CommentsSection';
import { useComments } from '@/hooks/useComments';

interface CommentsWrapperProps {
  entityType: 'test' | 'test_set' | 'test_run' | 'metric' | 'model' | 'prompt' | 'behavior' | 'category';
  entityId: string;
  sessionToken: string;
}

export default function CommentsWrapper({ entityType, entityId, sessionToken }: CommentsWrapperProps) {
  const {
    comments,
    isLoading,
    error,
    createComment,
    editComment,
    deleteComment,
    reactToComment,
    getCurrentUserId
  } = useComments({
    entityType,
    entityId
  });

  const currentUserId = getCurrentUserId();

  return (
    <Box>
      <CommentsSection
        entityType={entityType}
        entityId={entityId}
        comments={comments}
        onCreateComment={createComment}
        onEditComment={editComment}
        onDeleteComment={deleteComment}
        onReactToComment={reactToComment}
        currentUserId={currentUserId}
        isLoading={isLoading}
      />
    </Box>
  );
}
