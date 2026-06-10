'use client';

import React from 'react';
import { Box, Button, Typography } from '@mui/material';
import LinkIcon from '@mui/icons-material/Link';
import ArrowOutwardIcon from '@mui/icons-material/ArrowOutward';
import { useRouter } from 'next/navigation';
import { SectionCard } from '@/components/common/SectionCard';
import SectionEmptyState from '@/components/common/SectionEmptyState';
import ViewField from '@/components/common/ViewField';
import { Task } from '@/types/tasks';
import {
  buildLinkedEntityUrl,
  getEntityDisplayName,
  isValidEntityType,
} from '@/utils/entity-helpers';

interface TaskLinkedEntityTabProps {
  task: Task;
}

export default function TaskLinkedEntityTab({
  task,
}: TaskLinkedEntityTabProps) {
  const router = useRouter();
  const linkedUrl = buildLinkedEntityUrl(task);

  if (!task.entity_type || !task.entity_id || !linkedUrl) {
    return (
      <SectionCard>
        <SectionEmptyState
          icon={LinkIcon}
          title="No linked entity"
          description="This task is not linked to another record in Rhesis."
        />
      </SectionCard>
    );
  }

  const entityLabel = isValidEntityType(task.entity_type)
    ? getEntityDisplayName(task.entity_type)
    : task.entity_type;
  const navigationLabel = task.task_metadata?.comment_id
    ? 'Go to associated comment'
    : `Go to ${entityLabel}`;

  return (
    <SectionCard title="Linked entity">
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
        <Typography variant="body2" color="text.secondary">
          This task was created from or is associated with another record.
        </Typography>

        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
            gap: '30px',
          }}
        >
          <ViewField label="Entity type" value={entityLabel} />
          <ViewField label="Entity ID" value={task.entity_id} />
        </Box>

        <Box>
          <Button
            variant="outlined"
            endIcon={<ArrowOutwardIcon />}
            onClick={() => router.push(linkedUrl)}
            sx={{ textTransform: 'none' }}
          >
            {navigationLabel}
          </Button>
        </Box>
      </Box>
    </SectionCard>
  );
}
