'use client';

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Box, Typography, Button, Paper, Divider } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { Task, EntityType } from '@/types/tasks';
import { getTasksByEntity } from '@/utils/mock-data/tasks';
import { TasksSection } from './TasksSection';
import CommentsWrapper from '@/components/comments/CommentsWrapper';

interface TasksAndCommentsWrapperProps {
  entityType: EntityType;
  entityId: string;
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export function TasksAndCommentsWrapper({
  entityType,
  entityId,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TasksAndCommentsWrapperProps) {
  const router = useRouter();
  const [tasks, setTasks] = useState<Task[]>(() => getTasksByEntity(entityType, entityId));

  const handleCreateTask = useCallback(async (taskData: any) => {
    try {
      // In a real app, this would make an API call
      console.log('Creating task:', taskData);
      
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Create a new task with mock data
      const newTask: Task = {
        id: `task-${Date.now()}`,
        title: taskData.title,
        description: taskData.description,
        status: 'Open',
        priority: taskData.priority,
        creator_id: currentUserId,
        creator_name: currentUserName,
        assignee_id: taskData.assignee_id,
        assignee_name: taskData.assignee_id ? 'Assigned User' : undefined,
        entity_type: taskData.entity_type,
        entity_id: taskData.entity_id,
        comment_id: taskData.comment_id,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      };
      
      setTasks(prev => [...prev, newTask]);
    } catch (error) {
      console.error('Failed to create task:', error);
    }
  }, [currentUserId, currentUserName]);

  const handleEditTask = useCallback((taskId: string) => {
    // In a real app, this would navigate to the task detail page
    console.log('Edit task:', taskId);
    window.open(`/tasks/${taskId}`, '_blank');
  }, []);

  const handleDeleteTask = useCallback(async (taskId: string) => {
    try {
      // In a real app, this would make an API call
      console.log('Deleting task:', taskId);
      
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
      setTasks(prev => prev.filter(task => task.id !== taskId));
    } catch (error) {
      console.error('Failed to delete task:', error);
    }
  }, []);

  const handleCreateTaskFromComment = useCallback((commentId: string) => {
    // Navigate to create task page with entity and comment info
    const params = new URLSearchParams({
      entityType,
      entityId,
      commentId,
    });
    router.push(`/tasks/create?${params.toString()}`);
  }, [router, entityType, entityId]);

  const handleCreateTaskFromEntity = useCallback(() => {
    // Navigate to create task page with entity info
    const params = new URLSearchParams({
      entityType,
      entityId,
    });
    router.push(`/tasks/create?${params.toString()}`);
  }, [router, entityType, entityId]);

  return (
    <>
      {/* Tasks Section */}
      <TasksSection
        entityType={entityType}
        entityId={entityId}
        tasks={tasks}
        onCreateTask={handleCreateTask}
        onEditTask={handleEditTask}
        onDeleteTask={handleDeleteTask}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
      />

      {/* Comments Section with Task Creation Integration */}
      <CommentsWrapper
        entityType={entityType}
        entityId={entityId}
        sessionToken={sessionToken}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        currentUserPicture={currentUserPicture}
        onCreateTask={handleCreateTaskFromComment}
        onCreateTaskFromEntity={handleCreateTaskFromEntity}
      />
    </>
  );
}
