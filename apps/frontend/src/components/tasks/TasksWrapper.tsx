'use client';

import React, { useState, useCallback } from 'react';
import { Task, EntityType } from '@/types/tasks';
import { getTasksByEntity } from '@/utils/mock-data/tasks';
import { TasksSection } from './TasksSection';
import { TaskCreationModal } from './TaskCreationModal';

interface TasksWrapperProps {
  entityType: EntityType;
  entityId: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
}

export function TasksWrapper({
  entityType,
  entityId,
  currentUserId,
  currentUserName,
  currentUserPicture,
}: TasksWrapperProps) {
  const [tasks, setTasks] = useState<Task[]>(() => getTasksByEntity(entityType, entityId));
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleCreateTask = useCallback(async (taskData: any) => {
    setIsSubmitting(true);
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
      setShowCreateModal(false);
    } catch (error) {
      console.error('Failed to create task:', error);
    } finally {
      setIsSubmitting(false);
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

  return (
    <>
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

      {/* Task Creation Modal */}
      <TaskCreationModal
        open={showCreateModal}
        onClose={() => {
          setShowCreateModal(false);
          (window as any).pendingCommentId = undefined;
        }}
        onSubmit={handleCreateTask}
        entityType={entityType}
        entityId={entityId}
        currentUserId={currentUserId}
        currentUserName={currentUserName}
        isLoading={isSubmitting}
        commentId={(window as any).pendingCommentId}
      />
    </>
  );
}
