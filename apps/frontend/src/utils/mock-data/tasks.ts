import { Task, TaskStatus, TaskPriority, EntityType } from '@/types/tasks';

export const mockTasks: Task[] = [
  {
    id: 'task-1',
    title: 'Fix login validation issue',
    description: 'The login test is failing due to incorrect validation logic. Need to update the validation to handle edge cases properly.',
    status: 'Open',
    priority: 'High',
    creator_id: 'user-1',
    creator_name: 'Admin User',
    assignee_id: 'user-2',
    assignee_name: 'John Developer',
    entity_type: 'Test',
    entity_id: '4de45999-85a1-4409-a8f6-5b43b1328105',
    comment_id: 'comment-1',
    created_at: '2024-01-15T10:30:00Z',
    updated_at: '2024-01-15T10:30:00Z',
  },
  {
    id: 'task-2',
    title: 'Update test documentation',
    description: 'The test documentation needs to be updated to reflect the new API changes and include examples for the new endpoints.',
    status: 'In Progress',
    priority: 'Medium',
    creator_id: 'user-2',
    creator_name: 'John Developer',
    assignee_id: 'user-3',
    assignee_name: 'Jane Tester',
    entity_type: 'TestSet',
    entity_id: '431dc6c8-4be9-4f04-a028-ca1522caa282',
    created_at: '2024-01-14T14:20:00Z',
    updated_at: '2024-01-16T09:15:00Z',
  },
  {
    id: 'task-3',
    title: 'Investigate performance regression',
    description: 'Test run shows significant performance degradation compared to previous runs. Need to identify the root cause.',
    status: 'Completed',
    priority: 'High',
    creator_id: 'user-3',
    creator_name: 'Jane Tester',
    assignee_id: 'user-1',
    assignee_name: 'Admin User',
    entity_type: 'TestRun',
    entity_id: '1e783005-de73-40e6-b22a-26c53f12c8a0',
    comment_id: 'comment-2',
    created_at: '2024-01-13T16:45:00Z',
    updated_at: '2024-01-17T11:30:00Z',
    completed_at: '2024-01-17T11:30:00Z',
  },
  {
    id: 'task-4',
    title: 'Add error handling for edge cases',
    description: 'The current error handling doesn\'t cover all edge cases. Need to add comprehensive error handling.',
    status: 'Open',
    priority: 'Low',
    creator_id: 'user-1',
    creator_name: 'Admin User',
    entity_type: 'Test',
    entity_id: '4de45999-85a1-4409-a8f6-5b43b1328105',
    created_at: '2024-01-16T08:00:00Z',
    updated_at: '2024-01-16T08:00:00Z',
  },
  {
    id: 'task-5',
    title: 'Review and approve test results',
    description: 'Need to review the latest test results and approve them for the next release cycle.',
    status: 'Cancelled',
    priority: 'Medium',
    creator_id: 'user-2',
    creator_name: 'John Developer',
    assignee_id: 'user-3',
    assignee_name: 'Jane Tester',
    entity_type: 'TestRun',
    entity_id: '1e783005-de73-40e6-b22a-26c53f12c8a0',
    created_at: '2024-01-12T12:00:00Z',
    updated_at: '2024-01-18T14:20:00Z',
  },
  {
    id: 'task-6',
    title: 'Implement new test scenario',
    description: 'Add a new test scenario for the payment flow to ensure all edge cases are covered.',
    status: 'In Progress',
    priority: 'Medium',
    creator_id: 'user-3',
    creator_name: 'Jane Tester',
    assignee_id: 'user-2',
    assignee_name: 'John Developer',
    entity_type: 'TestSet',
    entity_id: '431dc6c8-4be9-4f04-a028-ca1522caa282',
    created_at: '2024-01-15T13:45:00Z',
    updated_at: '2024-01-17T10:20:00Z',
  },
  {
    id: 'task-7',
    title: 'Update CI/CD pipeline configuration',
    description: 'The CI/CD pipeline needs to be updated to handle the new test requirements and improve build times.',
    status: 'Open',
    priority: 'High',
    creator_id: 'user-1',
    creator_name: 'Admin User',
    assignee_id: 'user-1',
    assignee_name: 'Admin User',
    entity_type: 'TestRun',
    entity_id: '1e783005-de73-40e6-b22a-26c53f12c8a0',
    created_at: '2024-01-17T15:30:00Z',
    updated_at: '2024-01-17T15:30:00Z',
  },
  {
    id: 'task-8',
    title: 'Create comprehensive test coverage report',
    description: 'Generate a detailed test coverage report for the current sprint to identify gaps in testing.',
    status: 'Completed',
    priority: 'Low',
    creator_id: 'user-2',
    creator_name: 'John Developer',
    assignee_id: 'user-3',
    assignee_name: 'Jane Tester',
    entity_type: 'TestSet',
    entity_id: '431dc6c8-4be9-4f04-a028-ca1522caa282',
    created_at: '2024-01-10T09:00:00Z',
    updated_at: '2024-01-16T16:45:00Z',
    completed_at: '2024-01-16T16:45:00Z',
  },
];

export const mockUsers = [
  { id: 'user-1', name: 'Admin User', email: 'admin@example.com' },
  { id: 'user-2', name: 'John Developer', email: 'john@example.com' },
  { id: 'user-3', name: 'Jane Tester', email: 'jane@example.com' },
];

export const getTasksByEntity = (entityType: EntityType, entityId: string): Task[] => {
  return mockTasks.filter(task => 
    task.entity_type === entityType && task.entity_id === entityId
  );
};

export const getTasksByComment = (commentId: string): Task[] => {
  return mockTasks.filter(task => task.comment_id === commentId);
};

export const getTaskCountByComment = (commentId: string): number => {
  return mockTasks.filter(task => task.comment_id === commentId).length;
};

export const getTasksByStatus = (status: TaskStatus): Task[] => {
  return mockTasks.filter(task => task.status === status);
};

export const getTaskStats = () => {
  const total = mockTasks.length;
  const open = mockTasks.filter(task => task.status === 'Open').length;
  const inProgress = mockTasks.filter(task => task.status === 'In Progress').length;
  const completed = mockTasks.filter(task => task.status === 'Completed').length;
  const cancelled = mockTasks.filter(task => task.status === 'Cancelled').length;

  return { total, open, inProgress, completed, cancelled };
};
