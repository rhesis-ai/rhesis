'use client';

import React from 'react';
import { Box } from '@mui/material';
import { CommentsSection } from './CommentsSection';
import { useComments } from '@/hooks/useComments';
import { EntityType } from '@/types/comments';

interface CommentsWrapperProps {
  entityType: EntityType;
  entityId: string;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  onCreateTask?: (commentId: string) => void;
  onCreateTaskFromEntity?: () => void;
  onCountsChange?: () => void;
}

export default function CommentsWrapper({
  entityType,
  entityId,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
  onCreateTask,
  onCreateTaskFromEntity,
  onCountsChange,
}: CommentsWrapperProps) {
  const {
    comments,
    isLoading,
    error,
    createComment,
    editComment,
    deleteComment,
    reactToComment,
    refetch,
  } = useComments({
    entityType,
    entityId,
    sessionToken,
    currentUserId,
    currentUserName,
    currentUserPicture,
  });

  // Wrap the functions to match the expected Promise<void> return type
  const handleCreateComment = async (text: string): Promise<void> => {
    await createComment(text);
    // Notify parent that counts have changed
    await onCountsChange?.();
  };

  const handleEditComment = async (
    commentId: string,
    newText: string
  ): Promise<void> => {
    await editComment(commentId, newText);
  };

  const handleDeleteComment = async (commentId: string): Promise<void> => {
    await deleteComment(commentId);
    // Notify parent that counts have changed
    await onCountsChange?.();
  };

  const handleReactToComment = async (
    commentId: string,
    emoji: string
  ): Promise<void> => {
    await reactToComment(commentId, emoji);
  };

  return (
    <CommentsSection
      entityType={entityType}
      entityId={entityId}
      comments={comments}
      onCreateComment={handleCreateComment}
      onEditComment={handleEditComment}
      onDeleteComment={handleDeleteComment}
      onReactToComment={handleReactToComment}
      onCreateTask={onCreateTask}
      onCreateTaskFromEntity={onCreateTaskFromEntity}
      currentUserId={currentUserId}
      currentUserName={currentUserName}
      currentUserPicture={currentUserPicture}
      isLoading={isLoading}
    />
  );
}
