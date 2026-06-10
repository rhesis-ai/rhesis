'use client';

import React from 'react';
import { Box } from '@mui/material';
import DetailTabNav from '@/components/common/DetailTabNav';
import DetailTabPanel from '@/components/common/DetailTabPanel';
import CommentsWrapper from '@/components/comments/CommentsWrapper';
import { useDetailTabNav } from '@/hooks/useDetailTabNav';
import { Priority, Status, Task, TaskUpdate, User } from '@/types/tasks';
import TaskDetailsCard from './TaskDetailsCard';
import TaskLinkedEntityTab from './TaskLinkedEntityTab';

const TAB_KEYS = ['basic', 'linked', 'comments'] as const;

const TAB_LABELS: Record<(typeof TAB_KEYS)[number], string> = {
  basic: 'Basic Information',
  linked: 'Linked entities',
  comments: 'Comments',
};

interface TaskDetailTabsProps {
  task: Task;
  statuses: Status[];
  priorities: Priority[];
  users: User[];
  sessionToken: string;
  currentUserId: string;
  currentUserName: string;
  currentUserPicture?: string;
  onTaskUpdated: (task: Task) => void;
  updateTask: (id: string, data: TaskUpdate) => Promise<Task | undefined>;
}

export default function TaskDetailTabs({
  task,
  statuses,
  priorities,
  users,
  sessionToken,
  currentUserId,
  currentUserName,
  currentUserPicture,
  onTaskUpdated,
  updateTask,
}: TaskDetailTabsProps) {
  const { activeTab, handleTabChange } = useDetailTabNav(TAB_KEYS);

  const navTabs = TAB_KEYS.map((key, index) => ({
    key,
    label: TAB_LABELS[key],
    id: `task-detail-tab-${index}`,
    'aria-controls': `task-detail-tabpanel-${index}`,
  }));

  const handleSave = async (update: TaskUpdate) => updateTask(task.id, update);

  return (
    <Box>
      <DetailTabNav
        tabs={navTabs}
        activeIndex={activeTab}
        onChange={handleTabChange}
        aria-label="Task detail tabs"
      />

      <DetailTabPanel value={activeTab} index={0} prefix="task-detail">
        <TaskDetailsCard
          task={task}
          statuses={statuses}
          priorities={priorities}
          users={users}
          onSave={handleSave}
          onTaskUpdated={onTaskUpdated}
        />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={1} prefix="task-detail">
        <TaskLinkedEntityTab task={task} />
      </DetailTabPanel>

      <DetailTabPanel value={activeTab} index={2} prefix="task-detail">
        <CommentsWrapper
          entityType="Task"
          entityId={task.id}
          sessionToken={sessionToken}
          currentUserId={currentUserId}
          currentUserName={currentUserName}
          currentUserPicture={currentUserPicture}
        />
      </DetailTabPanel>
    </Box>
  );
}
